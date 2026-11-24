"""Entry point: python3 -m tinyhand_linux [tinyhand://link ...]"""
import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
