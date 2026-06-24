from __future__ import annotations

import sys

from ledit_core.interfaces import tui as _tui

sys.modules.setdefault("tui", _tui)
from ledit_core.frontends.cli.app import *  # noqa: E402,F403
