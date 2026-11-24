"""Welcome window for TinyHand Linux. Shows X11 input access instructions."""
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib


class WelcomeWindow(Gtk.Window):
    """Welcome window that guides user through X11 input access setup."""

    def __init__(self, on_done=None, simulate_untrusted=False):
        """
        Args:
            on_done: Optional callback called when user clicks Start (granted case).
            simulate_untrusted: If True, simulate that X11 access is not granted.
        """
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.on_done = on_done
        self.simulate_untrusted = simulate_untrusted
        self._timer = None

        self._build()
        self._refresh()

    @property
    def granted(self):
        """Check if X11 input access is available."""
        # On Linux, we assume it's granted unless simulate_untrusted is True
        # (real check would be done by input_tap module)
        return not self.simulate_untrusted

    def _build(self):
        """Build the window UI."""
        self.set_default_size(340, 300)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_accept_focus(True)

        # Create a container with rounded background
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._box.set_margin_top(20)
        self._box.set_margin_bottom(20)
        self._box.set_margin_start(20)
        self._box.set_margin_end(20)
        self.add(self._box)

        # Close button in top-right
        close_btn = Gtk.Button()
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.add(Gtk.Label(label="✕"))
        close_btn.get_style_context().add_class("close-button")
        close_btn.connect("clicked", self._on_close)
        close_btn.set_halign(Gtk.Align.END)
        close_btn.set_valign(Gtk.Align.START)
        close_btn.set_margin_top(10)
        close_btn.set_margin_end(10)
        self._box.pack_start(close_btn, False, False, 0)

        # Main content area with visual effect background
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content.set_halign(Gtk.Align.CENTER)
        content.set_valign(Gtk.Align.CENTER)
        self._box.pack_start(content, True, True, 0)

        # Icon placeholder
        self._icon = Gtk.Image()
        self._icon.set_from_file(str(
            self._get_icon_path()
        ))
        self._icon.set_pixel_size(76)
        content.pack_start(self._icon, False, False, 0)

        # Title
        self._title = Gtk.Label()
        self._title.set_halign(Gtk.Align.CENTER)
        self._title.get_style_context().add_class("title")
        content.pack_start(self._title, False, False, 0)

        # Subtitle
        self._subtitle = Gtk.Label()
        self._subtitle.set_halign(Gtk.Align.CENTER)
        self._subtitle.get_style_context().add_class("subtitle")
        content.pack_start(self._subtitle, False, False, 0)

        # Button
        self._button = Gtk.Button()
        self._button.set_halign(Gtk.Align.CENTER)
        self._button.set_margin_top(22)
        self._button.set_margin_bottom(12)
        self._button.connect("clicked", self._on_button_pressed)
        content.pack_start(self._button, False, False, 0)

        # Tip
        self._tip = Gtk.Label()
        self._tip.set_halign(Gtk.Align.CENTER)
        self._tip.get_style_context().add_class("tip")
        content.pack_start(self._tip, False, False, 0)

        # Add spacing after icon
        content.set_spacing(6)
        content.set_margin_top(16)

        # Set up CSS styling
        self._setup_css()

        # Connect close signal
        self.connect("delete-event", self._on_delete_event)

    def _get_icon_path(self):
        """Get the path to the app icon."""
        from . import paths
        icon_path = paths.ASSETS_DIR / "AppIcon.icon"
        if icon_path.exists():
            return icon_path
        # Try common icon names
        for name in ["tinyhand", "AppIcon", "app"]:
            for ext in ["png", "svg"]:
                candidate = paths.ASSETS_DIR / f"{name}.{ext}"
                if candidate.exists():
                    return candidate
        # Fallback to a simple placeholder
        return None

    def _setup_css(self):
        """Set up CSS styling for the window."""
        css = b"""
        window.welcome {
            background-color: rgba(0, 0, 0, 0);
        }
        box.content {
            background-color: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
        }
        label.title {
            font-size: 19px;
            font-weight: bold;
            margin-bottom: 6px;
        }
        label.subtitle {
            font-size: 13px;
            color: #666;
        }
        label.tip {
            font-size: 11px;
            color: #666;
        }
        button.close-button {
            background: none;
            border: none;
            font-size: 14px;
            color: #999;
            padding: 0;
            margin: 0;
        }
        button.close-button:hover {
            color: #333;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        style_context = self.get_style_context()
        style_context.add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _refresh(self):
        """Update UI based on granted state."""
        if self.granted:
            self._title.set_text("You're all set")
            self._subtitle.set_text("Press Ctrl+Alt+H any time to start.")
            self._button.get_child().set_text("Start")
            self._tip.set_text("Already on? Remove it and add it again.")
        else:
            self._title.set_text("Enable X11 input access")
            self._subtitle.set_text("TinyHand needs an X11 session (not Wayland) to work.")
            self._button.get_child().set_text("Continue")
            self._tip.set_text("")

    def _on_button_pressed(self, button):
        """Handle button click."""
        if self.granted:
            self._on_close(None, None)
            if self.on_done:
                self.on_done()
        else:
            # On Linux, the button just closes the window
            # (no settings panel to open like on macOS)
            self._on_close(None, None)

    def _on_close(self, widget, event=None):
        """Close the window."""
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        self.hide()

    def _on_delete_event(self, widget, event):
        """Handle window delete event."""
        self._on_close(None)
        return True

    def show(self):
        """Show the welcome window."""
        self.present()
        # Center the window
        self.set_position(Gtk.WindowPosition.CENTER)
        # Start refresh timer
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(500, self._refresh_timer)

    def _refresh_timer(self):
        """Timer callback for periodic refresh."""
        self._refresh()
        return True  # Continue timer
