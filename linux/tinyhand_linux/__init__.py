"""TinyHand for Linux (X11). See ../PORT_PLAN.md."""
import sys as _sys
from pathlib import Path as _Path

_root = _Path(__file__).resolve().parents[1]

# python-xlib may be vendored next to the package (see README).
_vendor = _root / "vendor"
if _vendor.is_dir() and str(_vendor) not in _sys.path:
    _sys.path.append(str(_vendor))
