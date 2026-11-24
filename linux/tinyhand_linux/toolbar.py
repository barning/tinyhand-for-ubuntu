"""Toolbar for TinyHand Linux. Floating bottom-center bar with style picker and controls."""
import gi
from dataclasses import dataclass
from typing import Optional, Callable, List, Tuple


gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib


class Toolbar(Gtk.Window):
    """Floating toolbar at the bottom of the screen.

    Provides pointer style picker, sound toggle, exit button, and hint display.
    """

    def __init__(
        self,
        on_style: Optional[Callable[[str], None]] = None,
        on_sound_toggle: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        """
        Args:
            on_style: Callback when a pointer style is selected (receives style_id).
            on_sound_toggle: Callback when sound toggle is clicked.
            on_exit: Callback when exit button is clicked.
        """
        super().__init__(type=Gtk.WindowType.TOPLEVEL)

        self.on_style = on_style
        self.on_sound_toggle = on_sound_toggle
        self.on_exit = on_exit

        # Current state
        self._current_style_id: Optional[str] = None
        self._sound_on = True
        self._needs_permission = False
        self._hint_panel: Optional[Gtk.Window] = None

        # Style buttons
        self._style_buttons: dict = {}  # style_id -> Gtk.Button

        self._build()
        self._refresh()

    def _build(self):
        """Build the toolbar UI."""
        # Configure window properties
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_accept_focus(False)

        # Main container
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._main_box.set_margin_start(10)
        self._main_box.set_margin_end(10)
        self._main_box.set_margin_top(8)
        self._main_box.set_margin_bottom(8)
        self.add(self._main_box)

        # Import pointer_style
        try:
            from . import pointer_style
            self._pointer_style = pointer_style
        except ImportError:
            # Will be provided by another worker; use a fallback
            self._pointer_style = None

        # Build style buttons
        self._build_style_buttons()

        # Divider
        divider = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self._main_box.pack_start(divider, False, False, 0)

        # Sound toggle button
        self._sound_btn = Gtk.Button()
        self._sound_btn.set_relief(Gtk.ReliefStyle.NONE)
        self._sound_btn.set_tooltip_text("Tap sound")
        self._sound_btn.connect("clicked", self._on_sound_toggle)
        self._main_box.pack_start(self._sound_btn, False, False, 0)

        # Exit button
        self._exit_btn = Gtk.Button()
        self._exit_btn.set_relief(Gtk.ReliefStyle.NONE)
        self._exit_btn.set_tooltip_text("Exit (Esc)")
        self._exit_btn.connect("clicked", self._on_exit)
        self._main_box.pack_start(self._exit_btn, False, False, 0)

        # Permission button
        self._permission_btn = Gtk.Button()
        self._permission_btn.set_relief(Gtk.ReliefStyle.NONE)
        self._permission_btn.set_tooltip_text(
            "TinyHand needs X11 input access to intercept clicks and draw"
        )
        self._permission_btn.connect("clicked", self._on_fix_permission)
        self._permission_btn.hide()
        self._main_box.pack_start(self._permission_btn, False, False, 0)

        # Set up styling
        self._setup_css()

        # Size request for buttons
        for child in self._main_box.get_children():
            if isinstance(child, Gtk.Button):
                child.set_size_request(40, 40)

        self._permission_btn.set_size_request(160, 32)

    def _build_style_buttons(self):
        """Build the pointer style selector buttons."""
        # Clear existing style buttons
        for child in list(self._main_box.get_children()):
            if child in self._style_buttons.values():
                self._main_box.remove(child)
        self._style_buttons = {}

        if self._pointer_style and hasattr(self._pointer_style, 'ALL_STYLES'):
            # Only the pinned styles go in the toolbar, as on macOS; the full list is in Settings.
            from . import prefs as _prefs
            pinned_ids = _prefs.Prefs().get('pinnedStyles') or []
            by_id = {st.id: st for st in self._pointer_style.ALL_STYLES}
            for style in [by_id[i] for i in pinned_ids if i in by_id]:
                btn = Gtk.Button()
                btn.set_relief(Gtk.ReliefStyle.NONE)
                btn.set_tooltip_text(style.name)
                btn.set_size_request(40, 40)
                btn.connect("clicked", self._on_style_clicked, style.id)

                # Try to load the image
                self._load_style_image(btn, style)

                self._style_buttons[style.id] = btn
                self._main_box.pack_start(btn, False, False, 0)
                self._main_box.reorder_child(btn, len(self._style_buttons) - 1)
        else:
            # Fallback: create a placeholder button
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_tooltip_text("Hand")
            btn.set_size_request(40, 40)
            btn.connect("clicked", self._on_style_clicked, "hand")
            self._style_buttons["hand"] = btn
            self._main_box.pack_start(btn, False, False, 0)

    def _load_style_image(self, button: Gtk.Button, style):
        """Load the image for a style button."""
        from . import paths

        if getattr(style, 'image_path', None) is not None:
            img_path = style.image_path
            if not img_path.is_absolute():
                img_path = paths.ASSETS_DIR / img_path
            if img_path.exists():
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(img_path))
                    # Hand PNGs are 1024x1536; a thumbnail keeps the button's natural size small.
                    scale = 26.0 / max(pixbuf.get_width(), pixbuf.get_height())
                    thumb = pixbuf.scale_simple(
                        max(1, int(pixbuf.get_width() * scale)),
                        max(1, int(pixbuf.get_height() * scale)),
                        GdkPixbuf.InterpType.BILINEAR,
                    )
                    img = Gtk.Image.new_from_pixbuf(thumb)
                    button.set_image(img)
                    return
                except Exception:
                    pass

        # Fallback: use a colored circle
        img = Gtk.Image()
        img.set_from_icon_name("input-mouse", Gtk.IconSize.MENU)
        button.set_image(img)

    def _setup_css(self):
        """Set up CSS styling for the toolbar."""
        css = b"""
        window.toolbar {
            background-color: rgba(0, 0, 0, 0);
        }
        box.toolbar {
            background-color: rgba(40, 40, 40, 0.95);
            border-radius: 16px;
        }
        button.toolbar-btn {
            background: none;
            border: none;
            border-radius: 10px;
        }
        button.toolbar-btn:hover {
            background-color: rgba(255, 255, 255, 0.18);
        }
        button.toolbar-btn.selected {
            background-color: rgba(255, 255, 255, 0.18);
        }
        button.permission {
            background-color: rgba(255, 165, 0, 0.9);
            border-radius: 10px;
            color: black;
            font-weight: bold;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        style_context = self.get_style_context()
        style_context.add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Apply toolbar class to main box
        self._main_box.get_style_context().add_class("toolbar")

    def _refresh(self):
        """Refresh button states."""
        # Update sound button icon
        self._update_sound_button()

        # Update style button selection
        if self._current_style_id and self._current_style_id in self._style_buttons:
            for style_id, btn in self._style_buttons.items():
                if style_id == self._current_style_id:
                    btn.get_style_context().add_class("selected")
                else:
                    btn.get_style_context().remove_class("selected")

    def _update_sound_button(self):
        """Update the sound button icon based on sound state."""
        icon_name = "audio-volume-high-symbolic" if self._sound_on else "audio-volume-muted-symbolic"
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        self._sound_btn.set_image(img)

        # Set a more appropriate icon if available
        try:
            if self._sound_on:
                icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic", Gtk.IconSize.MENU)
            else:
                icon = Gtk.Image.new_from_icon_name("audio-volume-muted-symbolic", Gtk.IconSize.MENU)
            self._sound_btn.set_image(icon)
        except:
            # Fallback to text
            self._sound_btn.set_label("🔊" if self._sound_on else "🔇")

    def _on_style_clicked(self, button, style_id: str):
        """Handle style button click."""
        if self.on_style:
            self.on_style(style_id)

    def _on_sound_toggle(self, button):
        """Handle sound toggle click."""
        if self.on_sound_toggle:
            self.on_sound_toggle()

    def _on_exit(self, button):
        """Handle exit button click."""
        if self.on_exit:
            self.on_exit()

    def _on_fix_permission(self, button):
        """Handle permission button click."""
        # No action needed for Linux - button just closes toolbar
        pass

    def select(self, style_id: str):
        """Select a pointer style by ID."""
        self._current_style_id = style_id
        self._refresh()

    def set_style(self, style_id: str):
        """Set the current pointer style (alias for select)."""
        self.select(style_id)

    def set_needs_permission(self, needed: bool):
        """Show or hide the permission button."""
        if needed == self._needs_permission:
            return
        self._needs_permission = needed
        if needed:
            self._permission_btn.show()
            self._permission_btn.set_label("  Allow clicks & drawing  ")
        else:
            self._permission_btn.hide()

    def show_hint(self, pairs: List[Tuple[str, str]]):
        """Show a hint row with key-value pairs.

        Args:
            pairs: List of (key, label) tuples to display.
        """
        self.hide_hint()

        # Create hint window
        hint = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        hint.set_decorated(False)
        hint.set_accept_focus(False)
        hint.set_skip_taskbar_hint(True)
        hint.set_type_hint(Gdk.WindowTypeHint.TOOLTIP)

        # Set window above toolbar
        hint.set_transient_for(self)
        hint.set_keep_above(True)

        # Main container
        hint_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        hint_box.set_margin_start(16)
        hint_box.set_margin_end(16)
        hint_box.set_margin_top(9)
        hint_box.set_margin_bottom(9)
        hint.add(hint_box)

        # Add each key-value pair
        for key, label in pairs:
            text = f"<b>{key}</b> {label}"
            lbl = Gtk.Label()
            lbl.set_markup(text)
            lbl.set_halign(Gtk.Align.START)
            hint_box.pack_start(lbl, False, False, 0)

        # Set up styling
        provider = Gtk.CssProvider()
        css = b"""
        window.hint {
            background-color: rgba(40, 40, 40, 0.95);
            border-radius: 12px;
        }
        label.hint {
            color: white;
            font-size: 12.5px;
        }
        """
        provider.load_from_data(css)
        hint.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Position hint above toolbar
        hint.set_size_request(300, 36)

        # Get screen geometry
        screen = self.get_screen()
        if screen:
            monitor = screen.get_primary_monitor()
            geom = screen.get_monitor_geometry(monitor)
            # Position hint above toolbar
            win_x, win_y = self.get_position()
            hint.move(win_x + self.get_allocated_width() // 2 - 150, win_y - 40)
        else:
            # Default position
            hint.move(100, 100)

        hint.show_all()
        hint.present()

        self._hint_panel = hint

        # Auto-hide after 3 seconds
        GLib.timeout_add(3000, self._hide_hint_delayed)

    def _hide_hint_delayed(self):
        """Hide hint after delay."""
        self.hide_hint()
        return False  # Remove timer

    def hide_hint(self):
        """Hide the current hint."""
        if self._hint_panel:
            self._hint_panel.destroy()
            self._hint_panel = None

    def set_sound(self, on: bool):
        """Set the sound toggle state.

        Args:
            on: True to enable sound, False to disable.
        """
        self._sound_on = on
        self._update_sound_button()

    def place(self, screen: Optional[Gdk.Screen] = None):
        """Place the toolbar on the given screen."""
        if screen is None:
            screen = self.get_screen()

        if screen:
            monitor = screen.get_primary_monitor()
            geom = screen.get_monitor_geometry(monitor)
            # get_default_size() is -1 unless set; use the natural size of the content.
            _, natural = self.get_preferred_size()
            win_w, win_h = natural.width, natural.height
            x = geom.x + geom.width // 2 - win_w // 2
            y = geom.y + geom.height - win_h - 14
            self.move(x, y)

    def show(self):
        """Show the toolbar."""
        self.place()
        self.show_all()
        self.present()

    def hide(self):
        """Hide the toolbar."""
        self.hide_hint()
        Gtk.Window.hide(self)
