#!/bin/sh
# Adds TinyHand to the app grid and the tinyhand:// links for the current user.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$APPS" "$ICONS"
cp "$REPO/assets/icon/hand-cursor.svg" "$ICONS/tinyhand.svg"
cat > "$APPS/tinyhand.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=TinyHand
GenericName=Pointer
Comment=A tiny hand that points at things on your screen
Exec=env GDK_BACKEND=x11 python3 -m tinyhand_linux %u
Path=$HERE
Icon=tinyhand
Terminal=false
Categories=Utility;Accessibility;
Keywords=pointer;hand;presentation;
StartupNotify=false
MimeType=x-scheme-handler/tinyhand;
DESK
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
xdg-mime default tinyhand.desktop x-scheme-handler/tinyhand 2>/dev/null || true
echo "TinyHand installed. Find it in the app grid. Log into an Xorg session to use it."
