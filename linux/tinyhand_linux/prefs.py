"""Preferences for TinyHand Linux. JSON at CONFIG_DIR/prefs.json."""
import json
from pathlib import Path
from typing import Any, Callable, Optional

from . import paths


# Default preferences matching Swift Preferences.swift
_DEFAULTS: dict[str, Any] = {
    "pointerSize": 0.13,
    "showShadow": True,
    "fadeSeconds": 3,
    "sound.hands": True,
    "sound.laser": False,
    "sound.tapSound": "thock",
    "interactKeepsHand": False,
    "doubleShiftClickThrough": True,
    "interactKey": "alt",
    "inkChoice": "match",
    "showToolbar": False,
    "showInkButton": True,
    "pinnedStyles": ["lavender", "glove", "coral", "plush", "robot", "laser"],
    "shortcut.toggle": {"keyCode": 4, "modifiers": 262144, "display": "Ctrl+Alt+H"},
    "shortcut.clear": {"keyCode": 24, "modifiers": 262144, "display": "Ctrl+Alt+X"},
}


class Prefs:
    """Singleton preferences with typed getters/setters and change callbacks."""
    
    _instance: Optional["Prefs"] = None
    _callbacks: dict[str, list[Callable[[Any], None]]] = {}
    
    def __new__(cls) -> "Prefs":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._data: dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load preferences from CONFIG_DIR/prefs.json."""
        paths.ensure_dirs()
        prefs_file = paths.CONFIG_DIR / "prefs.json"
        if prefs_file.exists():
            try:
                with open(prefs_file, "r") as f:
                    self._data = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._data = {}
        # Fill in defaults for missing keys
        for key, default in _DEFAULTS.items():
            if key not in self._data:
                self._data[key] = default
    
    def _save(self) -> None:
        """Save preferences to CONFIG_DIR/prefs.json."""
        paths.ensure_dirs()
        prefs_file = paths.CONFIG_DIR / "prefs.json"
        try:
            with open(prefs_file, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a preference value by key; falls back to the built-in default, then `default`."""
        return self._data.get(key, _DEFAULTS.get(key, default))
    
    def set(self, key: str, value: Any) -> None:
        """Set a preference value by key and trigger callbacks."""
        old = self._data.get(key)
        self._data[key] = value
        self._save()
        if old != value:
            self._notify(key, value)
    
    def on_change(self, key: str, fn: Callable[[Any], None]) -> None:
        """Register a callback for when a preference changes."""
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(fn)
    
    def _notify(self, key: str, value: Any) -> None:
        """Notify all callbacks for a key."""
        for callback in self._callbacks.get(key, []):
            try:
                callback(value)
            except Exception:
                pass
    
    def reset_all(self) -> None:
        """Reset all preferences to defaults."""
        # Clear the file first
        prefs_file = paths.CONFIG_DIR / "prefs.json"
        if prefs_file.exists():
            try:
                prefs_file.unlink()
            except OSError:
                pass
        # Reload defaults
        self._data = {}
        for key, default in _DEFAULTS.items():
            self._data[key] = default
        self._save()
        # Notify all callbacks with new values
        for key in _DEFAULTS:
            self._notify(key, self._data.get(key))
    
    # Typed property accessors matching Swift
    @property
    def pointer_size(self) -> float:
        return float(self.get("pointerSize"))
    
    @pointer_size.setter
    def pointer_size(self, value: float) -> None:
        self.set("pointerSize", value)
    
    @property
    def show_shadow(self) -> bool:
        return bool(self.get("showShadow"))
    
    @show_shadow.setter
    def show_shadow(self, value: bool) -> None:
        self.set("showShadow", value)
    
    @property
    def fade_seconds(self) -> float:
        return float(self.get("fadeSeconds"))
    
    @fade_seconds.setter
    def fade_seconds(self, value: float) -> None:
        self.set("fadeSeconds", value)
    
    @property
    def hand_sound(self) -> bool:
        return bool(self.get("sound.hands"))
    
    @hand_sound.setter
    def hand_sound(self, value: bool) -> None:
        self.set("sound.hands", value)
    
    @property
    def tap_sound(self) -> str:
        return str(self.get("sound.tapSound"))
    
    @tap_sound.setter
    def tap_sound(self, value: str) -> None:
        self.set("sound.tapSound", value)
    
    @property
    def laser_sound(self) -> bool:
        return bool(self.get("sound.laser"))
    
    @laser_sound.setter
    def laser_sound(self, value: bool) -> None:
        self.set("sound.laser", value)
    
    @property
    def interact_keeps_hand(self) -> bool:
        return bool(self.get("interactKeepsHand"))
    
    @interact_keeps_hand.setter
    def interact_keeps_hand(self, value: bool) -> None:
        self.set("interactKeepsHand", value)
    
    @property
    def double_shift_click_through(self) -> bool:
        return bool(self.get("doubleShiftClickThrough"))
    
    @double_shift_click_through.setter
    def double_shift_click_through(self, value: bool) -> None:
        self.set("doubleShiftClickThrough", value)
    
    @property
    def interact_key(self) -> str:
        return str(self.get("interactKey"))
    
    @interact_key.setter
    def interact_key(self, value: str) -> None:
        self.set("interactKey", value)
    
    @property
    def ink_choice(self) -> str:
        return str(self.get("inkChoice"))
    
    @ink_choice.setter
    def ink_choice(self, value: str) -> None:
        self.set("inkChoice", value)
    
    @property
    def show_toolbar(self) -> bool:
        return bool(self.get("showToolbar"))
    
    @show_toolbar.setter
    def show_toolbar(self, value: bool) -> None:
        self.set("showToolbar", value)
    
    @property
    def show_ink_button(self) -> bool:
        return bool(self.get("showInkButton"))
    
    @show_ink_button.setter
    def show_ink_button(self, value: bool) -> None:
        self.set("showInkButton", value)
    
    @property
    def pinned_styles(self) -> list[str]:
        return list(self.get("pinnedStyles"))
    
    @pinned_styles.setter
    def pinned_styles(self, value: list[str]) -> None:
        self.set("pinnedStyles", value)


# Module-level convenience functions
def get(key: str) -> Any:
    """Get a preference value by key."""
    return Prefs().get(key)


def set(key: str, value: Any) -> None:
    """Set a preference value by key."""
    Prefs().set(key, value)


def on_change(key: str, fn: Callable[[Any], None]) -> None:
    """Register a callback for when a preference changes."""
    Prefs().on_change(key, fn)


def reset_all() -> None:
    """Reset all preferences to defaults."""
    Prefs().reset_all()


if __name__ == "__main__":
    # Self-test: exercise core logic
    paths.ensure_dirs()
    
    # Reset to clean state for test
    prefs_file = paths.CONFIG_DIR / "prefs.json"
    if prefs_file.exists():
        prefs_file.unlink()
    
    # Need to reset the singleton for clean test
    Prefs._instance = None
    
    # Test defaults
    p = Prefs()
    assert p.pointer_size == 0.13
    assert p.show_shadow is True
    assert p.fade_seconds == 3
    assert p.hand_sound is True
    assert p.tap_sound == "thock"
    assert p.laser_sound is False
    assert p.interact_key == "alt"
    assert p.ink_choice == "match"
    assert p.show_toolbar is False
    assert p.pinned_styles == ["lavender", "glove", "coral", "plush", "robot", "laser"]
    
    # Test set/get
    p.pointer_size = 0.15
    assert p.pointer_size == 0.15
    
    # Test callback
    called = []
    def callback(val):
        called.append(val)
    
    p.on_change("pointerSize", callback)
    p.pointer_size = 0.16
    assert len(called) == 1
    assert called[0] == 0.16
    
    # Test persistence
    Prefs._instance = None
    p2 = Prefs()
    assert p2.pointer_size == 0.16
    
    # Reset
    p2.reset_all()
    Prefs._instance = None
    p3 = Prefs()
    assert p3.pointer_size == 0.13
    
    print("prefs.py self-test passed")
