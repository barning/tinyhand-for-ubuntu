"""The pointer overlay: a full-screen transparent window that draws the hand and ink.

Port of OverlayController.swift (core behaviour). While the pointer is on, the
overlay takes every mouse button press and drag, so nothing underneath gets
clicked. Holding the interact key (Alt) makes the overlay click-through by
emptying its X11 input shape, so clicks reach the app beneath, as on macOS.
Double-tapping Shift latches click-through on (and off again).

Not ported in v1: Space following, menu-bar detection, screen-lock detection,
and idle/timer pacing. The overlay redraws on a fixed GLib timer while it is on.
"""
from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, Gio, GdkX11, GLib, Gtk  # noqa: E402
from Xlib import X  # noqa: E402
from Xlib import display as xlib_display  # noqa: E402
from Xlib.ext import shape  # noqa: E402

from . import hotkeys, paths, pointer_style, prefs  # noqa: E402
from .arm_view import ArmView  # noqa: E402
from .log import log  # noqa: E402
from .tapsound import TapSound  # noqa: E402

TICK_MS = 16
ESCAPE_KEYSYM = "Escape"
HINT_MARKER = paths.DATA_DIR / "hint_shown"

# Ink colours from the macOS InkChoice enum (0xRRGGBB); "match" uses the pointer's own colour.
INK_CHOICES = {
    "red": 0xFF2E1F, "orange": 0xFF8A00, "yellow": 0xFFCC00, "green": 0x30C25A,
    "blue": 0x0A84FF, "purple": 0x8754F2, "white": 0xFFFFFF, "black": 0x1D1D21,
}
# Open-menu tracking: clicks pass through while a menu is open over the top panel.
# Verified with a real GTK menu (on while open, off after) and with no menu open.
MENU_TRACKING = False  # off while the tray-popup interaction is being checked


class Overlay:
    SHIFT_TAP_MAX = 0.3      # seconds a Shift press may last to count as a tap
    SHIFT_DOUBLE_MAX = 0.35  # seconds between two taps to count as a double tap

    def __init__(self) -> None:
        self._prefs = prefs.Prefs()
        self._window: Optional[Gtk.Window] = None
        self._arm: Optional[ArmView] = None
        self._toolbar = None
        self._timer_id: Optional[int] = None
        self._escape_id: Optional[int] = None
        self._down_button = False
        self._click_through = False
        self._latched = False  # double-Shift latch: every click reaches the app
        self._shift_down = False
        self._shift_down_at = 0.0
        self._last_shift_tap = 0.0
        self._xdisplay = None
        self._lock_sub = None
        self._top_inset = 0  # height of the top panel; clicks there reach the panel
        self._menu_open = False  # an override-redirect popup (a menu) sits over the top panel
        self._tick_count = 0
        self._style_id = self._prefs.get("selectedStyle") or "lavender"
        self.is_active = False
        self.on_active_changed: Optional[Callable[[], None]] = None
        self.on_needs_permission: Optional[Callable[[], None]] = None

    # ----- public API used by app.py --------------------------------------

    @property
    def style_id(self) -> str:
        return self._style_id

    def x11_ok(self) -> bool:
        display = Gdk.Display.get_default()
        return display is not None and type(display).__name__ == "X11Display"

    def attach_toolbar(self, toolbar) -> None:
        self._toolbar = toolbar

    def toggle(self) -> None:
        if self.is_active:
            self.deactivate()
        else:
            self.activate()

    def activate(self) -> bool:
        if self.is_active:
            return True
        if not self.x11_ok():
            log("activate skipped: not an X11 session")
            if self.on_needs_permission:
                self.on_needs_permission()
            return False
        self._ensure_window()
        self._apply_appearance()
        self.is_active = True
        self._window.move(0, 0)
        # Stays mapped between uses (see deactivate); shown and stuck to all workspaces once.
        if not self._window.get_visible():
            self._window.stick()  # on every workspace, like macOS Space following
            self._window.show_all()
        self._set_click_through(False)
        self._top_inset = self._measure_top_inset()
        self._watch_screen_lock()
        self._apply_cursor(hidden=True)
        self._arm.set_show_shadow(self._prefs.show_shadow)
        self._arm.pointer_hidden = False
        self._arm.held = False
        self._timer_id = GLib.timeout_add(TICK_MS, self._tick)
        self._escape_id = hotkeys.shared().register(ESCAPE_KEYSYM, 0, self.deactivate)
        TapSound.set_enabled(self._sound_on())
        self._show_toolbar()
        self._refresh_input_shape()
        self._notify()
        return True

    def deactivate(self) -> None:
        if not self.is_active:
            return
        self.is_active = False
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        if self._escape_id is not None:
            hotkeys.shared().unregister(self._escape_id)
            self._escape_id = None
        self._latched = False
        self._apply_cursor(hidden=False)
        self._down_button = False
        if self._arm is not None:
            self._arm.held = False
            self._arm.pointer_hidden = True  # draw nothing while off
            self._arm.ink.clear()
            self._arm.queue_draw()
        # Stay mapped but let every click through, so the desktop works while the pointer is off.
        self._set_click_through(True)
        if self._toolbar is not None:
            self._toolbar.hide()
        self._notify()

    def clear_ink(self) -> None:
        if self._arm is not None:
            self._arm.ink.clear()
            self._arm.queue_draw()

    def pick(self, style_id: str) -> None:
        style = pointer_style.style_by_id(style_id)
        if style is None:
            log(f"unknown pointer style {style_id!r}")
            return
        self._style_id = style_id
        self._prefs.set("selectedStyle", style_id)
        if self._arm is not None:
            self._arm.style = style
            self._apply_appearance()
            self._arm.queue_draw()
        if self._toolbar is not None:
            self._toolbar.select(style_id)

    def _apply_appearance(self) -> None:
        """Push pointer size, line fade and ink colour from preferences to the view."""
        if self._arm is None:
            return
        self._arm.set_hand_len_frac(float(self._prefs.get("pointerSize") or 0.13))
        self._arm.ink.fade_seconds = float(self._prefs.get("fadeSeconds") or 0)
        choice = str(self._prefs.get("inkChoice") or "match")
        if choice in INK_CHOICES:
            value = INK_CHOICES[choice]
            self._arm.ink.color = ((value >> 16 & 0xFF) / 255, (value >> 8 & 0xFF) / 255, (value & 0xFF) / 255)
        else:
            style = pointer_style.style_by_id(self._style_id)
            if style is not None:
                self._arm.ink.color = tuple(v / 255 for v in style.ink)
        self._arm.queue_draw()

    # ----- window ----------------------------------------------------------

    def _ensure_window(self) -> None:
        if self._window is not None:
            return
        root = Gdk.get_default_root_window()
        width, height = root.get_width(), root.get_height()

        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_title("TinyHand overlay")
        window.set_decorated(False)
        window.set_skip_taskbar_hint(True)
        window.set_skip_pager_hint(True)
        window.set_accept_focus(False)
        window.set_type_hint(Gdk.WindowTypeHint.DOCK)
        window.set_keep_above(True)
        window.set_app_paintable(True)
        window.set_default_size(width, height)
        screen = window.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None:
            window.set_visual(visual)

        arm = ArmView()
        arm.set_size_request(width, height)
        window.add(arm)
        window.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        window.connect("button-press-event", self._on_button_press)
        window.connect("button-release-event", self._on_button_release)
        window.connect("motion-notify-event", self._on_motion)
        window.connect("delete-event", lambda *_: True)

        style = pointer_style.style_by_id(self._style_id)
        if style is not None:
            arm.style = style

        self._window = window
        self._arm = arm
        self._prefs.on_change("pointerSize", lambda _v: self._apply_appearance())
        self._prefs.on_change("fadeSeconds", lambda _v: self._apply_appearance())
        self._prefs.on_change("inkChoice", lambda _v: self._apply_appearance())

    def _apply_cursor(self, hidden: bool) -> None:
        if self._window is None or self._window.get_window() is None:
            return
        display = self._window.get_display()
        cursor = None
        if hidden:
            cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR)
        self._window.get_window().set_cursor(cursor)

    def _show_toolbar(self) -> None:
        if self._toolbar is None:
            return
        if not self._prefs.show_toolbar:
            self._toolbar.hide()
            return
        self._toolbar.select(self._style_id)
        self._toolbar.set_sound(self._sound_on())
        self._toolbar.set_needs_permission(False)
        self._toolbar.place()
        self._toolbar.show()
        if not HINT_MARKER.exists():
            HINT_MARKER.parent.mkdir(parents=True, exist_ok=True)
            HINT_MARKER.write_text("1")
            pairs = [("Click", "to tap"), ("Drag", "to draw")]
            if self._prefs.interact_key != "off":
                pairs.append(("Hold Alt", "to click for real"))
            pairs.append(("Esc", "to exit"))
            self._toolbar.show_hint(pairs)
            GLib.timeout_add_seconds(10, self._hide_hint_once)

    def _hide_hint_once(self) -> bool:
        if self._toolbar is not None:
            self._toolbar.hide_hint()
        return False

    def _sound_on(self) -> bool:
        return bool(self._prefs.laser_sound if self._style_id == "laser" else self._prefs.hand_sound)

    def _notify(self) -> None:
        if self.on_active_changed:
            self.on_active_changed()

    # ----- input -----------------------------------------------------------

    def _on_button_press(self, _widget, event) -> bool:
        if self._click_through:
            return False
        x, y = event.x_root, event.y_root
        self._arm.set_position(x, y)
        self._arm.press()
        self._arm.held = True
        self._down_button = True
        if event.button == 1:
            self._arm.ink.begin(x, y)
        TapSound.play(self._style_id)
        if self._toolbar is not None:
            self._toolbar.hide_hint()
        self._arm.queue_draw()
        return True

    def _on_button_release(self, _widget, event) -> bool:
        if self._click_through:
            return False
        self._arm.held = False
        self._down_button = False
        self._arm.ink.end()
        self._arm.queue_draw()
        return True

    def _on_motion(self, _widget, event) -> bool:
        x, y = event.x_root, event.y_root
        self._arm.aim(x, y)
        if self._down_button and (event.state & Gdk.ModifierType.BUTTON1_MASK):
            self._arm.ink.extend(x, y)
        self._arm.queue_draw()
        return True

    def _tick(self) -> bool:
        if not self.is_active:
            return False
        root = Gdk.get_default_root_window()
        seat = Gdk.Display.get_default().get_default_seat()
        pointer = seat.get_pointer()
        _win, x, y, mask = root.get_device_position(pointer)
        self._arm.aim(x, y)
        self._arm.queue_draw()

        self._update_shift_latch(mask)
        # Clicks over the top bar are not passed through (that rule made the hand stick there).
        self._tick_count += 1
        if MENU_TRACKING and self._tick_count % 16 == 0:  # about four times a second
            self._menu_open = self._top_menu_open()
        held = self._interact_held(mask) or self._latched or self._menu_open
        if held != self._click_through:
            self._set_click_through(held)
        return True

    def _update_shift_latch(self, mask) -> None:
        """Double-tap Shift toggles the click-through latch (prefs doubleShiftClickThrough)."""
        import time

        shift = bool(mask & Gdk.ModifierType.SHIFT_MASK)
        now = time.monotonic()
        if shift and not self._shift_down:
            self._shift_down = True
            self._shift_down_at = now
        elif not shift and self._shift_down:
            self._shift_down = False
            if now - self._shift_down_at <= self.SHIFT_TAP_MAX:
                if now - self._last_shift_tap <= self.SHIFT_DOUBLE_MAX:
                    if self._prefs.get("doubleShiftClickThrough"):
                        self._latched = not self._latched
                    self._last_shift_tap = 0.0
                else:
                    self._last_shift_tap = now
            else:
                self._last_shift_tap = 0.0

    def _top_menu_open(self) -> bool:
        """True if a menu popup (an override-redirect window) is open over the top panel.

        This is how macOS passes clicks through while a menu-bar menu is open.
        """
        if self._top_inset <= 0:
            return False
        try:
            if self._xdisplay is None:
                self._xdisplay = xlib_display.Display()
            root = self._xdisplay.screen().root
            root_geom = root.get_geometry()
            root_w, root_h = root_geom.width, root_geom.height
            own = int(GdkX11.X11Window.get_xid(self._window.get_window())) if self._window else 0
            for child in root.query_tree().children:
                if child.id == own:
                    continue
                attrs = child.get_attributes()
                if not attrs.override_redirect or attrs.map_state != X.IsViewable:
                    continue
                geom = child.get_geometry()
                if geom.width >= root_w * 0.9 and geom.height >= root_h * 0.9:
                    continue  # full-screen compositor windows (e.g. mutter's guard window), not menus
                # A menu opens just under the panel: its top edge is near the panel, and it is
                # not a sliver (tooltips and tray icons are small).
                near_panel = geom.y <= self._top_inset + 80 and geom.y + geom.height > self._top_inset
                if near_panel and geom.width >= 40 and geom.height >= 40 and geom.width <= root_w * 0.5:
                    return True
        except Exception as error:  # the X connection can hiccup; keep the overlay running
            log(f"menu check failed: {error}")
        return False

    def _measure_top_inset(self) -> int:
        """Height of a panel docked at the top of the primary monitor (0 if none)."""
        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor is None:
            return 0
        geometry = monitor.get_geometry()
        workarea = monitor.get_workarea()
        return max(0, workarea.y - geometry.y)

    def _watch_screen_lock(self) -> None:
        """Turn the pointer off when the screen locks (GNOME and freedesktop screensaver signals)."""
        if self._lock_sub is not None:
            return
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return
        self._lock_sub = bus.signal_subscribe(
            None, "org.gnome.ScreenSaver", "ActiveChanged", "/org/gnome/ScreenSaver",
            None, Gio.DBusSignalFlags.NONE, self._on_lock_changed, None)

    def _on_lock_changed(self, _conn, _sender, _path, _iface, _signal, params, _data) -> None:
        locked = bool(params.unpack()[0])
        if locked and self.is_active:
            log("screen locked: turning the pointer off")
            self.deactivate()

    def _interact_held(self, mask) -> bool:
        """True while the chosen interact modifier is down (Alt by default)."""
        key = self._prefs.interact_key
        modifiers = {
            "control": Gdk.ModifierType.CONTROL_MASK,
            "command": Gdk.ModifierType.MOD4_MASK,  # Super
        }
        if key == "off":
            return False
        return bool(mask & modifiers.get(key, Gdk.ModifierType.MOD1_MASK))  # alt and legacy values

    def _set_click_through(self, on: bool) -> None:
        """Empty the window's X11 input shape so clicks pass through, or restore it."""
        self._click_through = on
        if self._window is None or self._window.get_window() is None:
            return
        xid = GdkX11.X11Window.get_xid(self._window.get_window())
        if self._xdisplay is None:
            self._xdisplay = xlib_display.Display()
        win = self._xdisplay.create_resource_object("window", xid)
        if on:
            # An empty input rectangle set: every event falls through the window.
            win.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, [])
        else:
            # A null mask resets the input shape to the whole window.
            win.shape_mask(shape.SO.Set, shape.SK.Input, 0, 0, X.NONE)
        self._xdisplay.flush()
        if self._arm is not None:
            self._arm.held = False

    def _refresh_input_shape(self) -> None:
        """Let clicks on the toolbar reach it: the overlay's input excludes the toolbar's rectangle."""
        if self._click_through or self._window is None or self._window.get_window() is None:
            return
        if self._toolbar is None or not self._toolbar.get_visible():
            return
        tx, ty = self._toolbar.get_position()
        tw, th = self._toolbar.get_size()
        width, height = self._window.get_size()
        # Four rectangles that cover the screen except for the toolbar.
        rects = [
            (0, 0, width, max(0, ty)),
            (0, ty, max(0, tx), th),
            (tx + tw, ty, max(0, width - tx - tw), th),
            (0, ty + th, width, max(0, height - ty - th)),
        ]
        rectangles = [{"x": x, "y": y, "width": w, "height": h} for x, y, w, h in rects if w > 0 and h > 0]
        xid = GdkX11.X11Window.get_xid(self._window.get_window())
        if self._xdisplay is None:
            self._xdisplay = xlib_display.Display()
        win = self._xdisplay.create_resource_object("window", xid)
        win.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, rectangles)
        self._xdisplay.flush()
