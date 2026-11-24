"""TinyHand application: tray icon, hotkeys, tinyhand:// links, wiring.

Port of AppDelegate.swift and main.swift. Uses a Gtk.Application so that a second
launch (for example `xdg-open tinyhand://toggle`) is forwarded to the running
instance through D-Bus and handled there.
"""
from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gio, Gtk  # noqa: E402

from . import automation, hotkeys, paths, prefs  # noqa: E402
from .log import log  # noqa: E402
from .overlay import Overlay  # noqa: E402
from .settings_window import SettingsWindow  # noqa: E402
from .tapsound import TapSound  # noqa: E402
from .toolbar import Toolbar  # noqa: E402
from .welcome import WelcomeWindow  # noqa: E402

APP_ID = "org.tinyhand.TinyHand"

# Default shortcuts, matching the macOS defaults (Control+Option+H, Control+Option+X).
DEFAULT_TOGGLE = {"keysym": "h", "modifiers": hotkeys.CONTROL | hotkeys.ALT}
DEFAULT_CLEAR = {"keysym": "x", "modifiers": hotkeys.CONTROL | hotkeys.ALT}


class TinyHandApp(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.overlay: Overlay | None = None
        self.toolbar: Toolbar | None = None
        self.settings: SettingsWindow | None = None
        self.welcome: WelcomeWindow | None = None
        self.tray: Gtk.StatusIcon | None = None
        self.sound_item: Gtk.CheckMenuItem | None = None
        self.toggle_item: Gtk.MenuItem | None = None
        self._hotkey_ids: list = []
        self._prefs = prefs.Prefs()

    # ----- lifecycle -------------------------------------------------------

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.hold()  # keep running with no visible window
        paths.ensure_dirs()
        log("starting TinyHand (Linux)")

        self.overlay = Overlay()
        self.overlay.on_active_changed = self._on_active_changed
        self.overlay.on_needs_permission = self._show_welcome

        self.toolbar = Toolbar(
            on_style=self._on_toolbar_style,
            on_sound_toggle=self._on_toolbar_sound,
            on_exit=self._exit_pointer,
        )
        self.overlay.attach_toolbar(self.toolbar)

        self._build_tray()
        self._register_hotkeys()
        self._prefs.on_change("sound.hands", lambda _v: self._refresh_menu())
        self._prefs.on_change("sound.laser", lambda _v: self._refresh_menu())
        self._refresh_menu()

        if not self.overlay.x11_ok():
            log("not running on X11: global input will not work")

    def do_activate(self) -> None:
        # No window of its own; the tray icon and hotkeys are the UI.
        pass

    def do_open(self, files, n_files, hint) -> None:
        self.activate()
        for gfile in files:
            url = gfile.get_uri()
            self._run_command(automation.parse_link(url), url)

    def do_shutdown(self) -> None:
        log("quitting TinyHand")
        if self.overlay is not None and self.overlay.is_active:
            self.overlay.deactivate()
        automation.StateFile.remove()
        hotkeys.shared().close()
        Gtk.Application.do_shutdown(self)

    # ----- tray ------------------------------------------------------------

    def _build_tray(self) -> None:
        self.tray = Gtk.StatusIcon()
        self.tray.connect("activate", lambda _icon: self.toggle_pointer())
        self.tray.connect("popup-menu", self._on_tray_popup)
        self._update_tray_icon()

        menu = Gtk.Menu()
        self.toggle_item = Gtk.MenuItem(label="Turn pointer on")
        self.toggle_item.connect("activate", lambda _i: self.toggle_pointer())
        menu.append(self.toggle_item)

        clear_item = Gtk.MenuItem(label="Clear drawing")
        clear_item.connect("activate", lambda _i: self.clear_ink())
        menu.append(clear_item)

        self.sound_item = Gtk.CheckMenuItem(label="Tap Sound")
        self.sound_item.connect("toggled", self._on_menu_sound_toggled)
        menu.append(self.sound_item)

        menu.append(Gtk.SeparatorMenuItem())

        settings_item = Gtk.MenuItem(label="Settings…")
        settings_item.connect("activate", lambda _i: self.show_settings())
        menu.append(settings_item)

        quit_item = Gtk.MenuItem(label="Quit TinyHand")
        quit_item.connect("activate", lambda _i: self.quit())
        menu.append(quit_item)
        menu.show_all()
        self._menu = menu

    def _on_tray_popup(self, icon, button, time) -> None:
        self._menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, time)

    def _update_tray_icon(self) -> None:
        on = bool(self.overlay and self.overlay.is_active)
        # White tray icons for the dark top bar (the PNGs in assets/ are black silhouettes).
        name = "tray-on.svg" if on else "tray-off.svg"
        self.tray.set_from_file(str(paths.ASSETS_DIR / "icon" / name))
        self.tray.set_tooltip_text(
            "TinyHand is on — click to turn off, right-click for the menu"
            if on else
            "TinyHand — click to turn on, right-click for the menu"
        )

    def _refresh_menu(self) -> None:
        if self.sound_item is None:
            return
        self.sound_item.handler_block_by_func(self._on_menu_sound_toggled)
        self.sound_item.set_active(self._sound_on())
        self.sound_item.handler_unblock_by_func(self._on_menu_sound_toggled)

    def _on_menu_sound_toggled(self, item) -> None:
        self._set_sound_on(item.get_active())

    def _on_active_changed(self) -> None:
        active = bool(self.overlay and self.overlay.is_active)
        if self.toggle_item is not None:
            self.toggle_item.set_label("Turn pointer off" if active else "Turn pointer on")
        self._update_tray_icon()
        self._write_state()

    # ----- hotkeys and actions ---------------------------------------------

    def _register_hotkeys(self) -> None:
        self._grab_shortcut("shortcut.toggle", DEFAULT_TOGGLE, self.toggle_pointer)
        self._grab_shortcut("shortcut.clear", DEFAULT_CLEAR, self.clear_ink)
        # Re-grab when Settings records a new shortcut.
        self._prefs.on_change("shortcut.toggle", lambda _v: self._regrab("shortcut.toggle"))
        self._prefs.on_change("shortcut.clear", lambda _v: self._regrab("shortcut.clear"))

    def _shortcut_for(self, key: str, default: dict) -> dict:
        value = self._prefs.get(key)
        return value if isinstance(value, dict) and value.get("keysym") else default

    def _grab_shortcut(self, key: str, default: dict, action) -> None:
        spec = self._shortcut_for(key, default)
        hid = hotkeys.shared().register(spec["keysym"], int(spec.get("modifiers", 0)), action)
        if hid is None and spec is not default:
            log(f"could not grab {spec.get('display', spec['keysym'])}; keeping the default")
            hid = hotkeys.shared().register(default["keysym"], default["modifiers"], action)
        self._hotkey_ids.append((key, hid, action))

    def _regrab(self, key: str) -> None:
        default = DEFAULT_TOGGLE if key == "shortcut.toggle" else DEFAULT_CLEAR
        for entry in list(self._hotkey_ids):
            k, hid, action = entry
            if k == key:
                if hid is not None:
                    hotkeys.shared().unregister(hid)
                self._hotkey_ids.remove(entry)
                self._grab_shortcut(key, default, action)
                break

    def toggle_pointer(self) -> None:
        if self.overlay is None:
            return
        self.overlay.toggle()

    def clear_ink(self) -> None:
        if self.overlay is not None:
            self.overlay.clear_ink()

    def _exit_pointer(self) -> None:
        if self.overlay is not None and self.overlay.is_active:
            self.overlay.deactivate()

    def _on_toolbar_style(self, style_id: str) -> None:
        if self.overlay is not None:
            self.overlay.pick(style_id)
        self._write_state()

    def _on_toolbar_sound(self, on: bool) -> None:
        self._set_sound_on(on)

    def _sound_on(self) -> bool:
        style = self.overlay.style_id if self.overlay else "lavender"
        return bool(self._prefs.laser_sound if style == "laser" else self._prefs.hand_sound)

    def _set_sound_on(self, on: bool) -> None:
        style = self.overlay.style_id if self.overlay else "lavender"
        if style == "laser":
            self._prefs.laser_sound = bool(on)
        else:
            self._prefs.hand_sound = bool(on)
        TapSound.set_enabled(bool(on))
        if self.toolbar is not None:
            self.toolbar.set_sound(bool(on))
        self._refresh_menu()
        self._write_state()

    def _write_state(self) -> None:
        if self.overlay is None:
            return
        style = self.overlay.style_id
        automation.StateFile.write(self.overlay.is_active, style, self._sound_on())

    # ----- windows ----------------------------------------------------------

    def show_settings(self) -> None:
        if self.settings is None:
            self.settings = SettingsWindow(self._prefs)
        self.settings.show()

    def _show_welcome(self) -> None:
        if self.welcome is None:
            self.welcome = WelcomeWindow(on_done=lambda: setattr(self, "welcome", None))
        self.welcome.show()
        self.welcome.present()

    # ----- tinyhand:// links ------------------------------------------------

    def _run_command(self, command, url: str) -> None:
        if command is None:
            log(f"ignoring link {url!r}")
            return
        action, arg = command.action, command.argument
        log(f"link action={action} arg={arg}")
        if self.overlay is None:
            return
        if action == "on":
            self.overlay.activate()
        elif action == "off":
            self.overlay.deactivate()
        elif action == "toggle":
            self.overlay.toggle()
        elif action == "clear":
            self.overlay.clear_ink()
        elif action == "style" and arg:
            self.overlay.pick(arg)
            self.overlay.activate()
        elif action == "sound":
            if arg == "on":
                self._set_sound_on(True)
            elif arg == "off":
                self._set_sound_on(False)
            elif arg == "toggle":
                self._set_sound_on(not self._sound_on())
        self._write_state()


def main(argv: list[str] | None = None) -> int:
    app = TinyHandApp()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
