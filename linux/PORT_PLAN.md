# TinyHand Linux port: plan and contracts

Target: Ubuntu, **X11 session** (Wayland can't capture global input or draw a global
click-through overlay, so it is out of scope for v1).

Stack: Python 3.12, PyGObject with GTK 3, cairo, Pillow, python-xlib (vendored in
`linux/vendor/`), and `pw-play`/`paplay`/`aplay` for sound.

Package root: `linux/tinyhand_linux/`, run with `python3 -m tinyhand_linux` from `linux/`.
The macOS `Sources/` tree is not modified.

## Modules

| Module | Swift source | Purpose |
|---|---|---|
| `paths.py` | (new) | `ASSETS_DIR`, `SOUNDS_DIR`, `CONFIG_DIR` (~/.config/tinyhand), `DATA_DIR` (~/.local/share/TinyHand) |
| `log.py` | Log.swift | `log(msg)` to `DATA_DIR/tinyhand.log` and stderr |
| `prefs.py` | Preferences.swift | `Prefs` with typed properties; JSON at `CONFIG_DIR/prefs.json`; `on_change(key, fn)` |
| `tapsound.py` | TapSound.swift | `TapSound.play(style_id)` via pw-play/paplay/aplay, non-blocking |
| `automation.py` | Automation.swift | `parse_link(url)`, `StateFile` for `DATA_DIR/state.json` |
| `pointer_style.py` | PointerStyle.swift | `PointerStyle`, `ALL_STYLES` (36 hands + laser), `style_by_id` |
| `handmaker.py` | HandMaker.swift | `make(path)`, `write(img, out)`, `HandProblem` (not yet restored) |
| `ink.py` | Ink.swift | `Ink`: strokes, cairo drawing, arrowhead |
| `arm_view.py` | ArmView.swift | `ArmView(Gtk.DrawingArea)`: hand/laser drawn at the pointer |
| `toolbar.py` | Toolbar.swift | `Toolbar(Gtk.Window)`: pinned pointers, sound, exit, hints |
| `welcome.py` | WelcomeWindow.swift | `WelcomeWindow`: X11 requirement notice |
| `settings_window.py` | SettingsView.swift + SettingsWindow.swift | `SettingsWindow(prefs)` with sections |
| `hotkeys.py` | HotKeyCenter.swift | `XGrabKey` global hotkeys read through a GLib watch |
| `overlay.py` | OverlayController.swift | Full-screen transparent overlay; XShape click-through; double-Shift latch |
| `app.py`, `__main__.py` | AppDelegate.swift, main.swift | Tray icon, hotkey re-grab, `tinyhand://` links |

## Behaviour to preserve

- Tap sound plays on click while sound is on.
- Hold Alt (or the chosen interact key) to click through; double-tap Shift to latch it.
- State file keys and link grammar as in the top-level `README.md`.
- Default shortcuts: Ctrl+Alt+H toggles, Ctrl+Alt+X clears, Esc turns the pointer off.

## Testing

- Pure modules have a `__main__` self-test: `cd linux && python3 -m tinyhand_linux.<module>`.
- GUI check: `GDK_BACKEND=x11 python3 -m tinyhand_linux`, then Ctrl+Alt+H, drag, Esc.
