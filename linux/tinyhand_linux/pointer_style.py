"""PointerStyle: definition of all pointer styles (hands and laser).

Port of PointerStyle.swift to Python.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import tinyhand_linux.paths as paths


# Ink color presets from Ink.swift
# Ink.purple = CGColor(srgbRed: 0.53, green: 0.33, blue: 0.95, alpha: 1)
# Ink.red = CGColor(srgbRed: 1.0, green: 0.16, blue: 0.12, alpha: 1)

PURPLE = (135, 84, 242)  # int(0.53*255), int(0.33*255), int(0.95*255)
RED = (255, 41, 31)  # int(1.0*255), int(0.16*255), int(0.12*255)


def _hex_to_rgb(hex_value: int) -> tuple:
    """Convert 0xRRGGBB to (R, G, B) tuple."""
    return ((hex_value >> 16) & 0xFF, (hex_value >> 8) & 0xFF, hex_value & 0xFF)


@dataclass(frozen=True)
class PointerStyle:
    """A pointer style definition.

    Attributes:
        id: Unique identifier (e.g., "lavender", "laser").
        name: Human-readable name.
        kind: One of "hand", "custom", or "laser".
        image_path: Path to the image file (None for laser).
        ink: RGB tuple for the ink/trail color.
    """
    id: str
    name: str
    kind: str
    image_path: Optional[Path]
    ink: tuple


# Built-in hand styles with their ink colors
# From PointerStyle.swift builtIn array
_BUILTIN_HANDS = [
    ("lavender", "Lavender toy", PURPLE),
    ("glove", "Cursor glove", PURPLE),
    ("coral", "Coral vinyl", RED),
    ("plush", "Plush", _hex_to_rgb(0x2F86F0)),
    ("robot", "Robot", _hex_to_rgb(0x16A87A)),
    ("pink", "Bubblegum", _hex_to_rgb(0xEE4F98)),
    ("blue", "Sky", _hex_to_rgb(0x2F86F0)),
    ("mint", "Mint", _hex_to_rgb(0x16A87A)),
    ("lemon", "Lemon", _hex_to_rgb(0xF2B705)),
    ("black", "Midnight", _hex_to_rgb(0x1D1D21)),
    ("chrome", "Chrome", _hex_to_rgb(0x6B7380)),
    ("holo", "Holo", PURPLE),
    ("fuzzy", "Fuzzy", PURPLE),
    ("wood", "Wood", _hex_to_rgb(0x9A5E2C)),
    ("marble", "Marble", _hex_to_rgb(0x6B7380)),
    ("terrazzo", "Terrazzo", _hex_to_rgb(0xF0561D)),
    ("glass", "Glass", _hex_to_rgb(0x1597E5)),
    ("jelly", "Jelly", _hex_to_rgb(0xA33FE6)),
    ("pastel", "Pastel", _hex_to_rgb(0xEE4F98)),
    ("pixel", "Pixel", _hex_to_rgb(0x1D1D21)),
    ("lowpoly", "Low poly", PURPLE),
    ("knit", "Knit", PURPLE),
    ("skeleton", "Skeleton", _hex_to_rgb(0x9A5E2C)),
    ("astro", "Astronaut", _hex_to_rgb(0x2F86F0)),
    ("space", "Space", RED),
    ("monster", "Monster", _hex_to_rgb(0x3E9E2E)),
    ("water", "Water", _hex_to_rgb(0x1597E5)),
    ("lava", "Lava", _hex_to_rgb(0xF0561D)),
    ("grass", "Grass", _hex_to_rgb(0x3E9E2E)),
    ("cactus", "Cactus", _hex_to_rgb(0x3E9E2E)),
    ("choco", "Chocolate", _hex_to_rgb(0x9A5E2C)),
    ("cloud", "Cloud", _hex_to_rgb(0x2F86F0)),
    ("mech", "Mech", _hex_to_rgb(0xF0561D)),
    ("neon", "Neon", _hex_to_rgb(0xE0309A)),
    ("leaf", "Leaf", _hex_to_rgb(0x3E9E2E)),
    ("cookie", "Gingerbread", _hex_to_rgb(0x9A5E2C)),
]

# Build ALL_STYLES: 36 hands + laser
ALL_STYLES: List[PointerStyle] = []

for hand_id, hand_name, ink_color in _BUILTIN_HANDS:
    image_path = paths.ASSETS_DIR / f"hand_{hand_id}.png"
    ALL_STYLES.append(PointerStyle(
        id=hand_id,
        name=hand_name,
        kind="hand",
        image_path=image_path,
        ink=ink_color,
    ))

# Laser pointer
ALL_STYLES.append(PointerStyle(
    id="laser",
    name="Laser dot",
    kind="laser",
    image_path=None,
    ink=RED,
))


def style_by_id(style_id: str) -> Optional[PointerStyle]:
    """Get a PointerStyle by its id.

    Args:
        style_id: The style identifier.

    Returns:
        The PointerStyle with matching id, or None if not found.
    """
    for style in ALL_STYLES:
        if style.id == style_id:
            return style
    return None


CUSTOM_DIR = paths.CONFIG_DIR / "custom_hands"
CUSTOM_LIST = CUSTOM_DIR / "hands.json"


def load_custom_styles() -> List[PointerStyle]:
    """Hands the user made with "Make your own", read from CONFIG_DIR/custom_hands."""
    import json

    try:
        entries = json.loads(CUSTOM_LIST.read_text())
    except (OSError, ValueError):
        return []
    styles = []
    for entry in entries:
        image = CUSTOM_DIR / f"{entry['id']}.png"
        if not image.exists():
            continue
        ink = tuple(entry.get("ink", RED))
        styles.append(PointerStyle(id=entry["id"], name=entry.get("name", entry["id"]),
                                   kind="custom", image_path=image, ink=ink))
    return styles


def reload_custom_styles() -> None:
    """Replace the custom entries in ALL_STYLES with what is on disk now."""
    ALL_STYLES[:] = [st for st in ALL_STYLES if st.kind != "custom"] + load_custom_styles()


ALL_STYLES.extend(load_custom_styles())


if __name__ == "__main__":
    """Self-test: verify all built-in styles and their assets."""
    import sys

    print(f"Total styles: {len(ALL_STYLES)}")
    print(f"Expected: 36 hands + 1 laser = 37")

    # Count by kind
    hands = [s for s in ALL_STYLES if s.kind == "hand"]
    laser_styles = [s for s in ALL_STYLES if s.kind == "laser"]
    custom_styles = [s for s in ALL_STYLES if s.kind == "custom"]

    print(f"  hand: {len(hands)}, laser: {len(laser_styles)}, custom: {len(custom_styles)}")

    # Check that all hand images exist
    assets_dir = paths.ASSETS_DIR
    missing = []
    for style in hands:
        if style.image_path:
            if not style.image_path.exists():
                missing.append(style.id)

    if missing:
        print(f"  MISSING hand images: {missing}")
    else:
        print(f"  All {len(hands)} hand images found")

    # Print some details
    print("\nInk colors:")
    for style in ALL_STYLES:
        if style.kind == "hand":
            print(f"  {style.id:12s} ({style.name:20s}): #{style.ink[0]:02x}{style.ink[1]:02x}{style.ink[2]:02x}")
        else:
            print(f"  {style.id:12s} ({style.name:20s}): #{style.ink[0]:02x}{style.ink[1]:02x}{style.ink[2]:02x} (laser)")

    # Test style_by_id
    print("\nTesting style_by_id:")
    for test_id in ["lavender", "laser", "nonexistent"]:
        s = style_by_id(test_id)
        print(f"  {test_id}: {'found' if s else 'NOT FOUND'}")

    # Test load_custom_styles
    customs = load_custom_styles()
    print(f"\nCustom styles: {len(customs)}")

    sys.exit(0 if len(ALL_STYLES) == 37 and not missing else 1)
