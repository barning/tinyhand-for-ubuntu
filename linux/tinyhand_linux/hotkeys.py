"""Global hotkeys for X11 (port of HotKeyCenter.swift).

Keys are grabbed on the root window with XGrabKey. Events are read from the X
connection through a GLib IO watch, so callbacks run on the GTK main loop.
Grabs are made for every combination of NumLock/CapsLock so the hotkeys still
work with those keys on.
"""
from __future__ import annotations

from typing import Callable, Dict

from gi.repository import GLib
from Xlib import X, XK, display as xdisplay
from Xlib.error import XError

from .log import log

SHIFT = X.ShiftMask
CONTROL = X.ControlMask
ALT = X.Mod1Mask  # Option on macOS
LOCK_MASKS = (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask)


class HotKeys:
    def __init__(self) -> None:
        self._display = xdisplay.Display()
        self._root = self._display.screen().root
        self._handlers: Dict[int, Callable[[], None]] = {}
        self._grabs: Dict[int, list] = {}
        self._next_id = 1
        self._by_code: Dict[tuple, int] = {}
        GLib.io_add_watch(self._display.fileno(), GLib.IO_IN, self._on_readable)

    def register(self, keysym_name: str, modifiers: int, action: Callable[[], None]) -> int | None:
        """Grab a key. keysym_name is an X keysym name such as 'h' or 'Escape'."""
        keysym = XK.string_to_keysym(keysym_name)
        if keysym == 0:
            log(f"hotkey: unknown key {keysym_name!r}")
            return None
        keycode = self._display.keysym_to_keycode(keysym)
        if not keycode:
            log(f"hotkey: no keycode for {keysym_name!r}")
            return None

        hotkey_id = self._next_id
        self._next_id += 1
        grabbed = []
        for extra in LOCK_MASKS:
            try:
                self._root.grab_key(keycode, modifiers | extra, True, X.GrabModeAsync, X.GrabModeAsync)
                grabbed.append((keycode, modifiers | extra))
            except XError as error:
                log(f"hotkey: grab failed for {keysym_name!r}: {error}")
                for code, mods in grabbed:
                    self._root.ungrab_key(code, mods)
                return None
        self._display.flush()

        self._handlers[hotkey_id] = action
        self._grabs[hotkey_id] = grabbed
        self._by_code[(keycode, modifiers & ~(X.LockMask | X.Mod2Mask))] = hotkey_id
        return hotkey_id

    def unregister(self, hotkey_id: int) -> None:
        for code, mods in self._grabs.pop(hotkey_id, []):
            try:
                self._root.ungrab_key(code, mods)
            except XError:
                pass
        self._handlers.pop(hotkey_id, None)
        for key, value in list(self._by_code.items()):
            if value == hotkey_id:
                del self._by_code[key]
        self._display.flush()

    def _on_readable(self, _fd, _condition) -> bool:
        try:
            while self._display.pending_events():
                event = self._display.next_event()
                if event.type == X.KeyPress:
                    self._dispatch(event)
        except XError as error:
            log(f"hotkey: X error {error}")
        return True

    def _dispatch(self, event) -> None:
        state = event.state & ~(X.LockMask | X.Mod2Mask)
        hotkey_id = self._by_code.get((event.detail, state))
        if hotkey_id is None:
            return
        handler = self._handlers.get(hotkey_id)
        if handler is not None:
            handler()

    def close(self) -> None:
        for hotkey_id in list(self._grabs):
            self.unregister(hotkey_id)
        self._display.close()


_shared: HotKeys | None = None


def shared() -> HotKeys:
    global _shared
    if _shared is None:
        _shared = HotKeys()
    return _shared


if __name__ == "__main__":
    # Manual check: press Ctrl+Alt+H, then Escape, to see the callbacks fire.
    from gi.repository import Gtk

    hk = shared()
    hk.register("h", CONTROL | ALT, lambda: print("ctrl+alt+h"))
    hk.register("Escape", 0, lambda: (print("escape"), Gtk.main_quit()))
    print("listening for Ctrl+Alt+H and Escape (Escape quits)")
    Gtk.main()
