from __future__ import annotations

import sys

from alpine_usb.interfaces.tui import *  # noqa: F403

if __name__ == "__main__":
    print("tui.py is import-only. Run ./ledit (or ./ledit tui).", file=sys.stderr)
    raise SystemExit(2)
