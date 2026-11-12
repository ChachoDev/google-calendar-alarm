"""Punto de entrada usado por PyInstaller (y equivalente a `calendar-alarm`)."""

from __future__ import annotations

import sys

from calendar_alarm.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
