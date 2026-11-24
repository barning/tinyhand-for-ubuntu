# TinyHand for Linux (X11)

A Linux port of TinyHand, the tiny hand that points at things on your screen. The
macOS app lives in `../Sources/TinyHand` and is unchanged. See `PORT_PLAN.md` for
the module layout.

## Requirements

- Ubuntu with an **X11 session**. Log out, pick "Ubuntu on Xorg" at the login
  screen, and log back in. Wayland can't capture global mouse input or draw a
  click-through overlay, so it isn't supported.
- Python 3.12 with GTK 3 bindings, Pillow and cairo bindings:

  ```sh
  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil pulseaudio-utils
  ```

  `python-xlib` is vendored in `linux/vendor/` (see below). `pulseaudio-utils`
  provides `paplay` for tap sounds; `pipewire-bin` provides `pw-play`, and either
  works.

## Run

```sh
cd linux
python3 -m tinyhand_linux
```

The tray icon appears in the top bar. Click it, or press **Ctrl+Alt+H**, to turn the
pointer on. Press **Esc** to turn it off.

## Shortcuts

| Keys | Action |
|---|---|
| Ctrl+Alt+H | Turn the pointer on or off |
| Ctrl+Alt+X | Clear the drawing |
| Esc | Clear everything and turn the pointer off (only while the pointer is on) |
| Click | Tap |
| Drag | Draw |
| Hold Alt | Click through to the app underneath |
| Double-tap Shift | Latch click-through on; double-tap again to turn it off |

## Links

As on macOS, `tinyhand://` links control a running instance. Install the desktop
entry once, so the scheme is routed to TinyHand:

```sh
cp tinyhand.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications
xdg-mime default tinyhand.desktop x-scheme-handler/tinyhand
```

```sh
xdg-open tinyhand://toggle
```

## Data locations

| Path | Contents |
|---|---|
| `~/.config/tinyhand/prefs.json` | Preferences |
| `~/.local/share/TinyHand/state.json` | Live state, removed on quit (same keys as the macOS app) |
| `~/.local/share/TinyHand/tinyhand.log` | Log |

## Status

Working: pointer overlay with hand tracking, drawing with fade, tap sound, the
toolbar (pinned pointers, sound, exit, can be hidden), hold-Alt and double-Shift
click-through, click-through over the top bar and open menus, Space following (all
workspaces), turn-off on screen lock, settings (six pages), recordable shortcuts,
launch at login, make-your-own hands, and `tinyhand://` links.

Checked on this desktop: hand tracking, drawing, fade, tap sound, toolbar, the
click-through rules, screen lock, a real GTK menu, and a window made fullscreen by
the window manager (the hand still draws over it).

Not yet confirmed:
- Drag-to-reorder of pinned pointers with a real mouse (arrow buttons also work).
- Make-your-own file picker, clicked through in the GUI.
- Multi-monitor layouts.

Known limits:
- X11 only. Under Wayland (XWayland) the desktop's full-screen guard window
  intercepts simulated clicks, which is why drag tests fail there.
- Shortcuts can be changed in Settings → General: click a shortcut button, then
  press the new keys (Escape cancels). Tested: a recorded Ctrl+Alt+J turns the
  pointer on.
- Double-tap Shift latches click-through; the Settings row for it is on.
- The macOS "Keep hand while interacting" option is not ported.
- No automatic updates. Update with `git pull` in the repository.

Recovery note: some files were rebuilt after an accidental deletion. `handmaker.py`
was rewritten from `Sources/TinyHand/HandMaker.swift`. The other rebuilt files were
recovered from build records and re-checked by the tests above. If behaviour differs
from the macOS app, the Swift source is the reference.

## Vendored python-xlib

If `python3-xlib` isn't installed system-wide, install it into `linux/vendor/`:

```sh
python3 -m pip install --target linux/vendor python-xlib
```

`tinyhand_linux` adds `linux/vendor` to the import path automatically.
