"""Filesystem locations shared by all TinyHand modules."""
import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2]

ASSETS_DIR = Path(os.environ.get("TINYHAND_ASSETS", REPO_DIR / "assets"))
SOUNDS_DIR = ASSETS_DIR / "sounds"

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "tinyhand"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "TinyHand"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
