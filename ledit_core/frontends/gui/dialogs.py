from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ledit_core.frontends.gui.icons import icon_label, make_app_icon, make_button_icon
from ledit_core.frontends.gui.theme import (
    BREEZE_BLUE,
    BREEZE_BLUE_HOVER,
    BREEZE_RED,
    BREEZE_RED_HOVER,
    BREEZE_TEXT,
    BREEZE_WINDOW,
    button_style,
)


def ensure_widget_visible(widget: QWidget, parent: QWidget | None = None):
    anchor = parent.window() if parent and parent.window() else parent
    screen = (
        (anchor.screen() if anchor and anchor.screen() else None) or widget.screen() or QApplication.primaryScreen()
    )
    if not screen:
        return
    available = screen.availableGeometry()
    widget.adjustSize()
    frame = widget.frameGeometry()
    if anchor and anchor.isVisible():
        # Use the top-level parent frame in global coordinates. This keeps
        # completion dialogs centered over the main app even after progress/status
        # widgets changed layout right before the modal opens.
        frame.moveCenter(anchor.frameGeometry().center())
    else:
        frame.moveCenter(available.center())
    x = max(available.left(), min(frame.left(), available.right() - frame.width() + 1))
    y = max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1))
    widget.move(x, y)


def exec_centered_dialog(box: QMessageBox, parent: QWidget | None = None):
    # Force a real Qt dialog (not macOS sheet/native panel), show it once so
    # geometry exists, then center/clamp it. This avoids AeroSpace/macOS placing
    # completion modals in a corner or another workspace.
    with contextlib.suppress(AttributeError):
        box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    box.setWindowModality(Qt.WindowModality.ApplicationModal)
    box.setWindowFlag(Qt.WindowType.Dialog, True)
    box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    box.adjustSize()
    box.show()
    QApplication.processEvents()
    ensure_widget_visible(box, parent)
    box.raise_()
    box.activateWindow()
    # Some macOS/tiling-WM combinations move transient dialogs after show().
    # Re-center a few times during dialog startup.
    QTimer.singleShot(0, lambda: ensure_widget_visible(box, parent))
    QTimer.singleShot(50, lambda: ensure_widget_visible(box, parent))
    QTimer.singleShot(150, lambda: ensure_widget_visible(box, parent))
    return box.exec()


def modal(parent, kind: str, title: str, text: str, question: bool = False) -> bool:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setWindowIcon(make_app_icon())
    dialog.setStyleSheet(
        f"QDialog {{ background:{BREEZE_WINDOW}; color:{BREEZE_TEXT}; }}"
        f"QLabel {{ color:{BREEZE_TEXT}; font-weight:400; background:transparent; }}"
    )

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(18, 16, 18, 14)
    outer.setSpacing(14)
    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)

    icon_kind = {"info": "check", "question": "warn", "error": "error"}.get(kind, "warn")
    icon = icon_label(icon_kind, 28)
    icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    body.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

    rich = "<" in text and ">" in text
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.RichText if rich else Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setMinimumWidth(420 if rich else 260)
    label.setMaximumWidth(520 if rich else 360)
    body.addWidget(label, 1)
    outer.addLayout(body)

    buttons = QHBoxLayout()
    buttons.addStretch(1)
    if question:
        cancel = QPushButton("Cancel")
        cancel.setIcon(make_button_icon("error"))
        cancel.setStyleSheet(button_style(BREEZE_RED, BREEZE_RED_HOVER).replace("3px 8px", "6px 12px"))
        ok = QPushButton("OK")
        ok.setIcon(make_button_icon("check"))
        ok.setStyleSheet(button_style(BREEZE_BLUE, BREEZE_BLUE_HOVER).replace("3px 8px", "6px 12px"))
        cancel.clicked.connect(dialog.reject)
        ok.clicked.connect(dialog.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        outer.addLayout(buttons)
        return exec_centered_dialog(dialog, parent) == QDialog.DialogCode.Accepted

    ok = QPushButton("OK")
    ok.setIcon(make_button_icon("check"))
    ok.setStyleSheet(button_style(BREEZE_BLUE, BREEZE_BLUE_HOVER).replace("3px 8px", "6px 12px"))
    ok.clicked.connect(dialog.accept)
    buttons.addWidget(ok)
    outer.addLayout(buttons)
    exec_centered_dialog(dialog, parent)
    return True
