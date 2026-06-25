from __future__ import annotations

import html
import os
import shutil
from pathlib import Path

from PySide6.QtWidgets import QComboBox

from ledit_core.frontends.gui.runtime import HOST_PATHS


def html_soft_break(value: object) -> str:
    return html.escape(str(value)).replace("/", "/<wbr>").replace("-", "-<wbr>")


def find_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for directory in HOST_PATHS:
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def combo_value(combo: QComboBox) -> str:
    data = combo.currentData()
    return str(data) if data not in (None, "") else combo.currentText().strip()


def add_combo_items(combo: QComboBox, items):
    labels = []
    for item in items:
        if isinstance(item, tuple):
            combo.addItem(item[0], item[1])
            labels.append(str(item[0]))
        else:
            combo.addItem(item)
            labels.append(str(item))
    if labels:
        try:
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            width = max(combo.fontMetrics().horizontalAdvance(label) for label in labels) + 56
            width = min(max(width, 120), 520)
            combo.setMinimumWidth(width)
            combo.view().setMinimumWidth(width)
        except Exception:
            pass
