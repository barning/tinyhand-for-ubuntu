"""Logging for TinyHand Linux. Writes to DATA_DIR/tinyhand.log and stderr."""
import sys
from datetime import datetime
from pathlib import Path

from . import paths


def log(msg: str) -> None:
    """Write a timestamped log message to DATA_DIR/tinyhand.log and stderr."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{timestamp} [{getpid()}] {msg}\n"
    log_file = paths.DATA_DIR / "tinyhand.log"
    paths.ensure_dirs()
    try:
        with open(log_file, "a") as f:
            f.write(line)
    except OSError:
        pass
    sys.stderr.write(line)


def getpid() -> int:
    """Get current process ID."""
    import os
    return os.getpid()


if __name__ == "__main__":
    # Self-test: exercise core logic
    from . import paths
    paths.ensure_dirs()
    log("Self-test: log.py writing test message")
    print("log.py self-test passed")
