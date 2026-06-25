#!/usr/bin/env python3
# ruff: noqa: I001
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ledit_core.frontends.gui.runtime import SCRIPT_DIR  # noqa: F401  # bootstrap Qt env before PySide imports

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ledit_core.frontends.gui.dialogs import ensure_widget_visible
from ledit_core.frontends.gui.icons import make_app_icon
from ledit_core.frontends.gui.main_window import Main
from ledit_core.frontends.gui.theme import apply_breeze_theme


def main() -> int:
    app = QApplication(sys.argv)
    apply_breeze_theme(app)
    app.setWindowIcon(make_app_icon())
    w = Main()
    w.show()
    QTimer.singleShot(0, lambda: ensure_widget_visible(w))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
