from __future__ import annotations

import sys

from alpine_usb.interfaces.cli import *  # noqa: F403
from alpine_usb.interfaces.cli import TERMINAL_ENTRYPOINT

if __name__ == "__main__":
    print(
        f"cli.py is import-only. Run ./{TERMINAL_ENTRYPOINT} (or ./{TERMINAL_ENTRYPOINT} tui).",
        file=sys.stderr,
    )
    raise SystemExit(2)
