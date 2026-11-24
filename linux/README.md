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

## Known limits (v1)

- X11 only.
- Shortcuts are fixed at Ctrl+Alt+H (toggle) and Ctrl+Alt+X (clear). The Settings
  shortcut buttons show them but can't record new ones yet.
- "Make your own hand" and drag-to-reorder for pointers are not available yet.
- No menu-bar detection, Space following, screen-lock detection.
- No automatic updates. Update with `git pull` in the repository.
- Overlay stacking over full-screen windows depends on the window manager.

## Vendored python-xlib

If `python3-xlib` isn't installed system-wide, install it into `linux/vendor/`:

```sh
python3 -m pip install --target linux/vendor python-xlib
```

`tinyhand_linux` adds `linux/vendor` to the import path automatically.
