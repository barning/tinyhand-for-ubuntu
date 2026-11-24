"""Automation for TinyHand Linux. Handles tinyhand:// links and state file."""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from . import paths


@dataclass
class Command:
    """Represents a parsed tinyhand:// command."""
    action: str
    argument: Optional[str] = None


# All built-in pointer styles with their type and name
# Based on PointerStyle.swift
BUILTIN_STYLES: list[dict[str, str]] = [
    {"id": "lavender", "name": "Lavender toy", "type": "hand"},
    {"id": "glove", "name": "Cursor glove", "type": "hand"},
    {"id": "coral", "name": "Coral vinyl", "type": "hand"},
    {"id": "plush", "name": "Plush", "type": "hand"},
    {"id": "robot", "name": "Robot", "type": "hand"},
    {"id": "pink", "name": "Bubblegum", "type": "hand"},
    {"id": "blue", "name": "Sky", "type": "hand"},
    {"id": "mint", "name": "Mint", "type": "hand"},
    {"id": "lemon", "name": "Lemon", "type": "hand"},
    {"id": "black", "name": "Midnight", "type": "hand"},
    {"id": "chrome", "name": "Chrome", "type": "hand"},
    {"id": "holo", "name": "Holo", "type": "hand"},
    {"id": "fuzzy", "name": "Fuzzy", "type": "hand"},
    {"id": "wood", "name": "Wood", "type": "hand"},
    {"id": "marble", "name": "Marble", "type": "hand"},
    {"id": "terrazzo", "name": "Terrazzo", "type": "hand"},
    {"id": "glass", "name": "Glass", "type": "hand"},
    {"id": "jelly", "name": "Jelly", "type": "hand"},
    {"id": "pastel", "name": "Pastel", "type": "hand"},
    {"id": "pixel", "name": "Pixel", "type": "hand"},
    {"id": "lowpoly", "name": "Low poly", "type": "hand"},
    {"id": "knit", "name": "Knit", "type": "hand"},
    {"id": "skeleton", "name": "Skeleton", "type": "hand"},
    {"id": "astro", "name": "Astronaut", "type": "hand"},
    {"id": "space", "name": "Space", "type": "hand"},
    {"id": "monster", "name": "Monster", "type": "hand"},
    {"id": "water", "name": "Water", "type": "hand"},
    {"id": "lava", "name": "Lava", "type": "hand"},
    {"id": "grass", "name": "Grass", "type": "hand"},
    {"id": "cactus", "name": "Cactus", "type": "hand"},
    {"id": "choco", "name": "Chocolate", "type": "hand"},
    {"id": "cloud", "name": "Cloud", "type": "hand"},
    {"id": "mech", "name": "Mech", "type": "hand"},
    {"id": "neon", "name": "Neon", "type": "hand"},
    {"id": "leaf", "name": "Leaf", "type": "hand"},
    {"id": "cookie", "name": "Gingerbread", "type": "hand"},
    {"id": "laser", "name": "Laser dot", "type": "laser"},
]


@dataclass
class State:
    """State file content matching README.md specification."""
    pid: int
    active: bool
    style: str
    soundOn: bool
    styles: list[dict[str, str]]


def parse_link(url: str) -> Optional[Command]:
    """Parse a tinyhand:// URL and return a Command or None.

    Supported commands (per README.md):
    - tinyhand://on, tinyhand://off, tinyhand://toggle
    - tinyhand://clear
    - tinyhand://style/<id>
    - tinyhand://sound/on, /off, /toggle
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() != "tinyhand":
        return None

    host = parsed.netloc.lower() if parsed.netloc else ""
    path = parsed.path.lstrip("/")

    if not host:
        return None

    if host in ("on", "off", "toggle", "clear"):
        return Command(action=host)

    if host == "style":
        # style/<id>
        if path:
            return Command(action="style", argument=path)
        return None

    if host == "sound":
        # sound/on, sound/off, sound/toggle, or sound/ (toggle)
        if path in ("on", "off", "toggle"):
            return Command(action="sound", argument=path)
        elif not path:
            return Command(action="sound", argument="toggle")
        return None

    return None


class StateFile:
    """Manages the state.json file at paths.DATA_DIR/state.json."""

    _instance: Optional["StateFile"] = None
    _state: Optional[State] = None

    def __new__(cls) -> "StateFile":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._state = None

    @classmethod
    def write(cls, active: bool, style: str, sound_on: bool) -> None:
        """Write state to DATA_DIR/state.json with same JSON keys as README.md.

        Keys: pid, active, style, soundOn, styles
        """
        paths.ensure_dirs()
        state = State(
            pid=os.getpid(),
            active=active,
            style=style,
            soundOn=sound_on,
            styles=BUILTIN_STYLES.copy(),
        )
        cls._state = state

        state_file = paths.DATA_DIR / "state.json"
        try:
            with open(state_file, "w") as f:
                json.dump(asdict(state), f, indent=2, sort_keys=True)
        except OSError:
            pass

    @classmethod
    def remove(cls) -> None:
        """Remove the state file."""
        state_file = paths.DATA_DIR / "state.json"
        if state_file.exists():
            try:
                state_file.unlink()
            except OSError:
                pass
        cls._state = None

    @classmethod
    def read(cls) -> Optional[State]:
        """Read the current state from the state file."""
        if cls._state is not None:
            return cls._state

        state_file = paths.DATA_DIR / "state.json"
        if not state_file.exists():
            return None

        try:
            with open(state_file, "r") as f:
                data = json.load(f)
                return State(
                    pid=data.get("pid", 0),
                    active=data.get("active", False),
                    style=data.get("style", ""),
                    soundOn=data.get("soundOn", False),
                    styles=data.get("styles", []),
                )
        except (OSError, json.JSONDecodeError, KeyError):
            return None


if __name__ == "__main__":
    # Self-test: exercise core logic
    paths.ensure_dirs()

    # Test parse_link
    tests = [
        ("tinyhand://toggle", Command(action="toggle")),
        ("tinyhand://on", Command(action="on")),
        ("tinyhand://off", Command(action="off")),
        ("tinyhand://clear", Command(action="clear")),
        ("tinyhand://style/lavender", Command(action="style", argument="lavender")),
        ("tinyhand://sound/on", Command(action="sound", argument="on")),
        ("tinyhand://sound/off", Command(action="sound", argument="off")),
        ("tinyhand://sound/toggle", Command(action="sound", argument="toggle")),
        ("tinyhand://sound", Command(action="sound", argument="toggle")),
        ("http://example.com", None),
        ("tinyhand://", None),
        ("tinyhand://unknown", None),
    ]

    for url, expected in tests:
        result = parse_link(url)
        if expected is None:
            assert result is None, f"Expected None for {url}, got {result}"
        else:
            assert result is not None, f"Expected Command for {url}, got None"
            assert result.action == expected.action, f"Action mismatch for {url}"
            assert result.argument == expected.argument, f"Argument mismatch for {url}"

    # Test state file
    StateFile.write(active=True, style="lavender", sound_on=True)
    state = StateFile.read()
    assert state is not None
    assert state.active is True
    assert state.style == "lavender"
    assert state.soundOn is True
    assert state.pid == os.getpid()
    assert len(state.styles) > 0

    StateFile.remove()
    state = StateFile.read()
    assert state is None

    print("automation.py self-test passed")
