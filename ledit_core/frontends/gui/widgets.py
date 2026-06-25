from __future__ import annotations

import platform

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ledit_core.frontends.gui.icons import make_button_icon
from ledit_core.frontends.gui.theme import (
    BREEZE_BLUE,
    BREEZE_BLUE_HOVER,
    BREEZE_BORDER,
    BREEZE_GREEN,
    BREEZE_GREEN_HOVER,
    BREEZE_PANEL,
    BREEZE_RED,
    BREEZE_RED_HOVER,
    BREEZE_TEXT,
    BREEZE_VIEW,
    button_style,
)
from ledit_core.frontends.gui.workers import DeviceScanWorker


class DeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select USB device")
        self.resize(620, 380)
        self.selected = None
        self.scanner = None
        layout = QVBoxLayout(self)
        title = QLabel("Select target USB device")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        self.empty_usb_message = QLabel("No USB devices found. Please connect a drive and rescan.")
        self.empty_usb_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_usb_message.setStyleSheet(
            f"background:{BREEZE_VIEW};color:{BREEZE_TEXT};border:1px solid {BREEZE_BORDER};font-size:15pt;font-weight:bold;"
        )
        self.empty_usb_message.hide()
        layout.addWidget(self.empty_usb_message, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Manual device:"))
        self.manual = QLineEdit()
        self.manual.setPlaceholderText("/dev/disk7" if platform.system() == "Darwin" else "/dev/sdX")
        row.addWidget(self.manual, 1)
        layout.addLayout(row)
        btns = QHBoxLayout()
        self.use = QPushButton("Use selected")
        self.use.setIcon(make_button_icon("check"))
        self.use.setStyleSheet(button_style(BREEZE_GREEN, BREEZE_GREEN_HOVER).replace("3px 8px", "6px 12px"))
        self.refresh = QPushButton("Refresh")
        self.refresh.setIcon(make_button_icon("refresh"))
        self.refresh.setStyleSheet(button_style(BREEZE_BLUE, BREEZE_BLUE_HOVER).replace("3px 8px", "6px 12px"))
        self.cancel = QPushButton("Cancel")
        self.cancel.setIcon(make_button_icon("error"))
        self.cancel.setStyleSheet(button_style(BREEZE_RED, BREEZE_RED_HOVER).replace("3px 8px", "6px 12px"))
        btns.addWidget(self.use)
        btns.addWidget(self.refresh)
        btns.addStretch()
        btns.addWidget(self.cancel)
        layout.addLayout(btns)
        self.use.clicked.connect(self.accept_selection)
        self.refresh.clicked.connect(lambda: self.populate())
        self.cancel.clicked.connect(self.reject)
        self.list.itemSelectionChanged.connect(self.update_use_button)
        self.manual.textChanged.connect(self.update_use_button)
        self.populate()

    def populate(self):
        if self.scanner and self.scanner.isRunning():
            return
        self.devices = []
        self.list.clear()
        self.list.hide()
        self.empty_usb_message.setText("Scanning for USB devices…")
        self.empty_usb_message.show()
        self.refresh.setEnabled(False)
        self.refresh.setText("Scanning…")
        self.use.setEnabled(False)
        self.scanner = DeviceScanWorker(self)
        self.scanner.done.connect(self.scan_done)
        self.scanner.finished.connect(self.scan_finished)
        self.scanner.start()

    def scan_done(self, devices):
        self.devices = devices
        self.list.clear()
        if self.devices:
            self.empty_usb_message.hide()
            self.list.show()
            for dev, label in self.devices:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, dev)
                self.list.addItem(item)
        else:
            self.list.hide()
            self.empty_usb_message.setText("No USB devices found. Please connect a drive and rescan.")
            self.empty_usb_message.show()
        self.list.clearSelection()
        self.update_use_button()

    def scan_finished(self):
        self.refresh.setEnabled(True)
        self.refresh.setText("Refresh")
        if self.sender() is self.scanner:
            self.scanner = None

    def update_use_button(self):
        self.use.setEnabled(bool(self.list.currentItem() or self.manual.text().strip()))

    def accept_selection(self):
        item = self.list.currentItem()
        manual = self.manual.text().strip()
        if item:
            self.selected = item.text()
        elif manual:
            self.selected = manual
        else:
            return
        self.accept()

    def closeEvent(self, event):
        if self.scanner and self.scanner.isRunning():
            event.ignore()
            return
        event.accept()


class CollapsibleSection(QWidget):
    def __init__(self, title: str, collapsed: bool = True, parent=None, icon_kind: str | None = None):
        super().__init__(parent)
        self.title = title
        self.dirty = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.toggle = QPushButton()
        if icon_kind:
            self.toggle.setIcon(make_button_icon(icon_kind, 18))
            self.toggle.setIconSize(QSize(18, 18))
        self.toggle.setCheckable(True)
        self.toggle.setChecked(not collapsed)
        self.toggle.clicked.connect(self.update_state)
        self.toggle.setStyleSheet(
            f"text-align:left;font-size:14px;color:{BREEZE_TEXT};"
            "margin:0px;padding:6px 10px;"
            f"background:{BREEZE_PANEL};border:1px solid {BREEZE_BORDER};border-radius:6px;"
        )
        root.addWidget(self.toggle)
        self.body = QWidget()
        self.body.setObjectName("sectionBody")
        self.body.setStyleSheet(
            f"QWidget#sectionBody {{ background:{BREEZE_VIEW};border:1px solid {BREEZE_BORDER};border-top:0;"
            "border-top-left-radius:0px;border-top-right-radius:0px;"
            "border-bottom-left-radius:6px;border-bottom-right-radius:6px; }"
        )
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 10, 10, 10)
        self.body_layout.setSpacing(8)
        root.addWidget(self.body)
        self.body.setVisible(not collapsed)
        self.update_state()

    def update_state(self):
        expanded = self.toggle.isChecked()
        self.body.setVisible(expanded)
        dot = "  ●" if self.dirty else ""
        self.toggle.setText(f"{self.title}{dot}  {'▼' if expanded else '▲'}")
        if expanded:
            self.toggle.setStyleSheet(
                f"text-align:left;font-size:14px;color:{BREEZE_TEXT};"
                "margin:0px;padding:6px 10px;"
                f"background:{BREEZE_PANEL};border:1px solid {BREEZE_BORDER};border-bottom:0;"
                "border-top-left-radius:6px;border-top-right-radius:6px;"
                "border-bottom-left-radius:0px;border-bottom-right-radius:0px;"
            )
        else:
            self.toggle.setStyleSheet(
                f"text-align:left;font-size:14px;color:{BREEZE_TEXT};"
                "margin:0px;padding:6px 10px;"
                f"background:{BREEZE_PANEL};border:1px solid {BREEZE_BORDER};border-radius:6px;"
            )

    def set_dirty(self, dirty: bool):
        if self.dirty == dirty:
            return
        self.dirty = dirty
        self.update_state()


class PackageSuggestionList(QListWidget):
    accept_suggestion = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Right, Qt.Key.Key_Tab):
            self.accept_suggestion.emit()
            return
        super().keyPressEvent(event)


class PasswordLineEdit(QLineEdit):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal_button = QToolButton(self)
        self.reveal_button.setCursor(Qt.CursorShape.ArrowCursor)
        self.reveal_button.setIcon(make_button_icon("eye", 16))
        self.reveal_button.setIconSize(QSize(16, 16))
        self.reveal_button.setToolTip("Show password")
        self.reveal_button.setFixedSize(22, 22)
        self.reveal_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.reveal_button.setStyleSheet("QToolButton { background:transparent;border:0;padding:0;margin:0; }")
        self.reveal_button.clicked.connect(self.toggle_password_visible)
        self.setTextMargins(0, 0, 28, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        x = self.rect().right() - self.reveal_button.width() - 5
        y = (self.rect().height() - self.reveal_button.height()) // 2
        self.reveal_button.move(x, y)

    def toggle_password_visible(self):
        show = self.echoMode() == QLineEdit.EchoMode.Password
        self.setEchoMode(QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password)
        self.reveal_button.setIcon(make_button_icon("eye_off" if show else "eye", 16))
        self.reveal_button.setToolTip("Hide password" if show else "Show password")
