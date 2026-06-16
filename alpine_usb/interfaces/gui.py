#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# This module can be executed directly after the dev GUI bootstrap re-execs into
# .qtvenv. In that path, sys.path[0] is alpine_usb/interfaces, so add project
# root before importing sibling screaming-architecture packages.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alpine_usb.apk_packages.index import BRANCH_RE, search_official_apk_packages, validate_extra_packages
from alpine_usb.usb_devices.detection import device_safety_report, list_devices


def secure_runtime_dir(name: str) -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    base = Path(tempfile.gettempdir()) / f"alpine-usb-installer-{uid}"
    for path in [base, base / name]:
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlinked runtime path: {path}")
        if path.exists():
            st = path.stat()
            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                raise RuntimeError(f"Refusing runtime path not owned by current user: {path}")
            if stat.S_IMODE(st.st_mode) & 0o077:
                path.chmod(0o700)
        else:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    return base / name


def prepare_frozen_runtime(bundle_dir: Path) -> Path:
    """Copy bundled build resources to a writable, stable directory.

    PyInstaller app bundles keep data files inside the .app internals. Docker
    Desktop can fail to mount those paths reliably, and the build scripts also
    create work files next to themselves. Use /tmp/alpine-usb-installer/app-runtime
    instead and make sure required files/directories exist there.
    """
    runtime = secure_runtime_dir("app-runtime")
    for name in [
        "build-alpine-usb.sh",
        "configure-alpine-usb.sh",
        "README.md",
        "LICENSE",
        "scripts/Dockerfile.builder",
    ]:
        src = bundle_dir / name
        if src.exists():
            dst = runtime / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if name.endswith(".sh"):
                dst.chmod(0o755)
    src_efi = bundle_dir / "efi-fallback"
    dst_efi = runtime / "efi-fallback"
    if src_efi.exists():
        if dst_efi.exists():
            shutil.rmtree(dst_efi)
        shutil.copytree(src_efi, dst_efi)
    work = runtime / ".work"
    work.mkdir(exist_ok=True)
    work.chmod(0o700)
    return runtime


if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    SCRIPT_DIR = prepare_frozen_runtime(BUNDLE_DIR)
else:
    SCRIPT_DIR = PROJECT_ROOT
    QT_VENV_PYTHON = SCRIPT_DIR / ".qtvenv" / "bin" / "python"
    if Path(sys.executable).resolve() != QT_VENV_PYTHON.resolve():
        if not QT_VENV_PYTHON.exists():
            subprocess.check_call([sys.executable, "-m", "venv", str(SCRIPT_DIR / ".qtvenv")])
            requirements = SCRIPT_DIR / "requirements.txt"
            if requirements.exists():
                subprocess.check_call(
                    [
                        str(QT_VENV_PYTHON),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "-r",
                        str(requirements),
                    ]
                )
            else:
                subprocess.check_call(
                    [str(QT_VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "PySide6_Essentials"]
                )
        os.execv(str(QT_VENV_PYTHON), [str(QT_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
os.chdir(SCRIPT_DIR)

# Finder-launched macOS apps get a minimal PATH. Add common CLI locations so
# Docker Desktop and Nix/Homebrew tools are discoverable from the standalone app.
HOST_PATHS = [
    "/run/current-system/sw/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/Applications/Docker.app/Contents/Resources/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
]
os.environ["PATH"] = os.pathsep.join([p for p in HOST_PATHS if Path(p).exists()] + [os.environ.get("PATH", "")])

from PySide6.QtCore import QEvent, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_TITLE = "Alpine USB Installer"
DEFAULT_IMAGE_NAME = "alpine-usb.img"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "alpine-usb-installer"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / DEFAULT_IMAGE_NAME
SAVED_CONFIG_PATH = Path.home() / ".config" / "alpine-usb-installer" / "gui-config.json"


def make_app_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(QColor("#111827"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(QColor("#93c5fd"))
    painter.drawRoundedRect(10, 8, 44, 48, 8, 8)
    painter.setBrush(QColor("#16a34a"))
    painter.setPen(QColor("#bbf7d0"))
    painter.drawRoundedRect(22, 4, 20, 12, 4, 4)
    painter.setPen(QColor("#ffffff"))
    painter.drawLine(24, 34, 32, 24)
    painter.drawLine(32, 24, 40, 34)
    painter.drawLine(32, 24, 32, 44)
    painter.end()
    return QIcon(pix)


def make_button_icon(kind: str, size: int = 20) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 20
    pen = QPen(QColor("#ffffff"), max(2, int(2 * scale)))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    def pts(items):
        return [QPoint(x, y) for x, y in items]

    def xy(v):
        return int(v * scale)

    if kind == "folder":
        p.drawPolyline(
            pts(
                [
                    (xy(3), xy(7)),
                    (xy(3), xy(16)),
                    (xy(17), xy(16)),
                    (xy(17), xy(6)),
                    (xy(9), xy(6)),
                    (xy(7), xy(4)),
                    (xy(3), xy(4)),
                    (xy(3), xy(7)),
                ]
            )
        )
    elif kind == "build":
        p.drawLine(xy(10), xy(3), xy(10), xy(14))
        p.drawLine(xy(6), xy(7), xy(10), xy(3))
        p.drawLine(xy(14), xy(7), xy(10), xy(3))
        p.drawLine(xy(4), xy(16), xy(16), xy(16))
    elif kind == "usb":
        p.drawLine(xy(10), xy(3), xy(10), xy(14))
        p.drawLine(xy(6), xy(7), xy(14), xy(7))
        p.drawEllipse(xy(5), xy(6), xy(2), xy(2))
        p.drawRect(xy(13), xy(5), xy(3), xy(3))
        p.drawEllipse(xy(8), xy(14), xy(4), xy(4))
    elif kind == "flash":
        p.drawPolyline(
            pts(
                [
                    (xy(11), xy(2)),
                    (xy(5), xy(11)),
                    (xy(10), xy(11)),
                    (xy(8), xy(18)),
                    (xy(15), xy(8)),
                    (xy(10), xy(8)),
                    (xy(11), xy(2)),
                ]
            )
        )
    elif kind == "refresh":
        p.drawArc(xy(5), xy(5), xy(10), xy(10), 35 * 16, 285 * 16)
        p.drawLine(xy(14), xy(5), xy(14), xy(9))
        p.drawLine(xy(14), xy(5), xy(10), xy(5))
    elif kind == "check":
        p.drawLine(xy(4), xy(10), xy(8), xy(15))
        p.drawLine(xy(8), xy(15), xy(16), xy(5))
    elif kind == "warn":
        p.drawPolyline(pts([(xy(10), xy(3)), (xy(18), xy(17)), (xy(2), xy(17)), (xy(10), xy(3))]))
        p.drawLine(xy(10), xy(7), xy(10), xy(12))
        p.drawPoint(xy(10), xy(15))
    elif kind == "error":
        p.drawEllipse(xy(3), xy(3), xy(14), xy(14))
        p.drawLine(xy(7), xy(7), xy(13), xy(13))
        p.drawLine(xy(13), xy(7), xy(7), xy(13))
    p.end()
    return QIcon(pix)


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
    try:
        box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
    except AttributeError:
        pass
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
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setWindowIcon(make_app_icon())
    icon_kind = {"info": "check", "question": "warn", "error": "error"}.get(kind, "warn")
    box.setIconPixmap(make_button_icon(icon_kind, 40).pixmap(40, 40))
    if question:
        ok = box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        ok.setIcon(make_button_icon("check"))
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        cancel.setIcon(make_button_icon("error"))
        cancel.setStyleSheet(
            "background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;"
        )
        ok.setStyleSheet(
            "background:#2563eb;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;"
        )
        exec_centered_dialog(box, parent)
        return box.clickedButton() == ok
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok = box.button(QMessageBox.StandardButton.Ok)
    if ok:
        ok.setIcon(make_button_icon("check"))
        ok.setStyleSheet(
            "background:#2563eb;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;"
        )
    exec_centered_dialog(box, parent)
    return True


def find_executable(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for directory in HOST_PATHS:
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


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


class DeviceScanWorker(QThread):
    done = Signal(list)

    def run(self):
        self.done.emit(list_devices())


class ApkSearchWorker(QThread):
    done = Signal(str, list)
    failed = Signal(str, str)

    def __init__(self, branch: str, arch: str, query: str):
        super().__init__()
        self.branch = branch
        self.arch = arch
        self.query = query

    def run(self):
        try:
            self.done.emit(self.query, search_official_apk_packages(self.branch, self.arch, self.query, limit=10))
        except Exception as exc:
            self.failed.emit(self.query, str(exc))


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
            "background:#0b1220;color:#ffffff;border:1px solid #374151;font-size:15pt;font-weight:bold;"
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
        self.refresh = QPushButton("Refresh")
        self.refresh.setIcon(make_button_icon("refresh"))
        self.cancel = QPushButton("Cancel")
        self.cancel.setIcon(make_button_icon("error"))
        self.cancel.setStyleSheet(
            "background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;"
        )
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
    def __init__(self, title: str, collapsed: bool = True, parent=None):
        super().__init__(parent)
        self.title = title
        self.dirty = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.toggle = QPushButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(not collapsed)
        self.toggle.clicked.connect(self.update_state)
        self.toggle.setStyleSheet(
            "text-align:left;font-size:14px;font-weight:bold;color:#93c5fd;"
            "margin:0px;padding:6px 10px;background:#1f2937;"
            "border:1px solid #374151;border-radius:6px;"
        )
        root.addWidget(self.toggle)
        self.body = QWidget()
        self.body.setObjectName("sectionBody")
        self.body.setStyleSheet(
            "QWidget#sectionBody { background:#0b1220;border:1px solid #374151;border-top:0;"
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
                "text-align:left;font-size:14px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:6px 10px;background:#1f2937;"
                "border:1px solid #374151;border-bottom:0;"
                "border-top-left-radius:6px;border-top-right-radius:6px;"
                "border-bottom-left-radius:0px;border-bottom-right-radius:0px;"
            )
        else:
            self.toggle.setStyleSheet(
                "text-align:left;font-size:14px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:6px 10px;background:#1f2937;"
                "border:1px solid #374151;border-radius:6px;"
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


SECRET_ENV_TO_FILE = {
    "ALPINE_USB_PASSWORD": "ALPINE_USB_PASSWORD_FILE",
    "ALPINE_USB_ROOT_PASSWORD": "ALPINE_USB_ROOT_PASSWORD_FILE",
}


def prepare_secret_env(env: dict[str, str]) -> tuple[dict[str, str], list[Path]]:
    safe_env = dict(env)
    created: list[Path] = []
    secret_dir = SCRIPT_DIR / ".work" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(0o700)
    for key, file_key in SECRET_ENV_TO_FILE.items():
        value = safe_env.pop(key, "")
        path = secret_dir / f"{key.lower()}-{os.getpid()}.secret"
        path.write_text(value)
        path.chmod(0o600)
        safe_env[file_key] = str(path)
        created.append(path)
    return safe_env, created


def cleanup_secret_files(paths: list[Path]):
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


class BuildWorker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, config_env: dict[str, str], output_path: str):
        super().__init__()
        self.config_env = config_env
        self.output_path = output_path

    def run(self):
        try:
            env = os.environ.copy()
            safe_config_env, secret_files = prepare_secret_env({k: str(v) for k, v in self.config_env.items()})
            env.update(safe_config_env)
            env.setdefault("IMAGE_NAME", DEFAULT_IMAGE_NAME)
            final = str(Path(self.output_path).expanduser().resolve())
            Path(final).parent.mkdir(parents=True, exist_ok=True)
            env["OUTPUT_PATH"] = final
            if os.path.exists(final):
                os.remove(final)
            script = SCRIPT_DIR / "build-alpine-usb.sh"
            if not script.exists():
                raise RuntimeError(f"Build script not found: {script}")
            script.chmod(0o755)
            configure = SCRIPT_DIR / "configure-alpine-usb.sh"
            if configure.exists():
                configure.chmod(0o755)
            cmd = [str(script)]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=str(SCRIPT_DIR)
            )
            for line in proc.stdout or []:
                self.log.emit(line.rstrip())
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"Build failed with exit code {code}")
            if not os.path.exists(final):
                raise RuntimeError(f"Build finished but expected image was not found: {final}")
            self.done.emit(True, f"Image build complete: {final}")
        except Exception as e:
            self.done.emit(False, str(e))
        finally:
            cleanup_secret_files(locals().get("secret_files", []))


class FlashWorker(QThread):
    log = Signal(str)
    progress = Signal(str)
    done = Signal(bool, str)

    def __init__(self, image: str, label: str, sudo_password: str | None = None):
        super().__init__()
        self.image = image
        self.label = label
        self.sudo_password = sudo_password

    def selected_device(self):
        if self.label.startswith("/dev/"):
            return self.label.split()[0]
        m = re.match(r"(/dev/\S+)", self.label)
        return m.group(1) if m else None

    def run(self):
        try:
            dev = self.selected_device()
            if not dev:
                raise RuntimeError("Invalid USB device")
            ok_safe, dev, _rows, reason = device_safety_report(dev)
            if not ok_safe:
                raise RuntimeError(reason or "Unsafe USB target")
            if platform.system() == "Darwin":
                raw = dev.replace("/dev/disk", "/dev/rdisk")
                image_for_dd = self.image
                log_path = os.path.join(tempfile.gettempdir(), "alpine-usb-flash.log")
                try:
                    os.remove(log_path)
                except FileNotFoundError:
                    pass
                total = os.path.getsize(image_for_dd)
                if not self.sudo_password:
                    raise RuntimeError("Administrator password is required to flash the USB.")
                with open(log_path, "w") as log:
                    log.write("Alpine USB Installer - Flash USB\n")
                    log.write(f"Target: {dev}\nImage: {image_for_dd}\n\n")
                auth = subprocess.run(
                    ["sudo", "-S", "-v"],
                    input=self.sudo_password + "\n",
                    text=True,
                    capture_output=True,
                )
                if auth.returncode != 0:
                    raise RuntimeError("Invalid administrator password or sudo was cancelled.")
                with open(log_path, "a") as log:
                    subprocess.run(["diskutil", "unmountDisk", dev], stdout=log, stderr=subprocess.STDOUT, text=True)
                    log.flush()
                    inner = (
                        f"/bin/dd if={sh_quote(image_for_dd)} of={sh_quote(raw)} bs=16m & "
                        "ddpid=$!; "
                        "while kill -0 $ddpid 2>/dev/null; do kill -INFO $ddpid 2>/dev/null || true; sleep 2; done; "
                        "wait $ddpid"
                    )
                    proc = subprocess.Popen(
                        ["sudo", "-S", "/bin/sh", "-c", inner],
                        stdin=subprocess.PIPE,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    if proc.stdin:
                        proc.stdin.write(self.sudo_password + "\n")
                        proc.stdin.close()
                    pos = 0
                    last_percent = -1
                    started = time.monotonic()
                    self.progress.emit("Flashing... 0%")
                    while proc.poll() is None:
                        pos, last_percent = self.tail_progress(log_path, pos, total, last_percent, started)
                        self.msleep(500)
                    log.flush()
                    pos, last_percent = self.tail_progress(log_path, pos, total, last_percent, started)
                    if proc.returncode:
                        raise RuntimeError(f"Flashing failed with exit code {proc.returncode}")
                    subprocess.run(["sync"])
                    subprocess.run(["diskutil", "eject", dev], stdout=log, stderr=subprocess.STDOUT, text=True)
                self.done.emit(True, "DONE. USB flashed and ejected.")
            elif platform.system() == "Linux":
                cmd = [
                    "dd",
                    f"if={self.image}",
                    f"of={dev}",
                    "bs=16M",
                    "iflag=fullblock",
                    "status=progress",
                    "conv=fsync",
                ]
                if os.geteuid() != 0:
                    cmd.insert(0, shutil.which("pkexec") or "sudo")
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout or []:
                    self.log.emit(line.rstrip())
                    m = re.search(r"(\d+) bytes", line)
                    if m:
                        self.progress.emit(f"Flashing... {m.group(1)} bytes written")
                if proc.wait() != 0:
                    raise RuntimeError("Flashing failed")
                self.done.emit(True, "DONE. USB flashed.")
            else:
                raise RuntimeError("Windows flashing not implemented. Use Rufus/balenaEtcher.")
        except Exception as e:
            self.done.emit(False, str(e))
        finally:
            # Keep the sudo password only for the active flash operation.
            self.sudo_password = None

    def tail_progress(self, log_path: str, pos: int, total: int, last_percent: int, started: float):
        if not os.path.exists(log_path):
            return pos, last_percent
        with open(log_path, errors="ignore") as fh:
            fh.seek(pos)
            data = fh.read()
            pos = fh.tell()
        for line in data.splitlines():
            self.log.emit(line)
            m = re.search(r"(\d+) bytes", line)
            if m and total:
                written = int(m.group(1))
                percent = min(100, int(written * 100 / total))
                if percent != last_percent:
                    elapsed = max(0.001, time.monotonic() - started)
                    mib_s = written / elapsed / (1024 * 1024)
                    remaining = max(0, total - written)
                    eta = int(remaining / max(1, written / elapsed))
                    self.progress.emit(f"Flashing... {percent}% ({written} bytes, {mib_s:.1f} MiB/s, ETA {eta}s)")
                    last_percent = percent
        return pos, last_percent


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(make_app_icon())
        self.resize(1120, 760)

        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.image = QLineEdit(str(DEFAULT_OUTPUT_PATH))
        self.image.setPlaceholderText(f"Output image path, e.g. {DEFAULT_OUTPUT_PATH}")
        self.device = QLineEdit()
        self.status = QLabel("")
        self.status.setStyleSheet("color:#d1d5db;")
        self.status.hide()
        self.build_status = QLabel("")
        self.build_status.setStyleSheet("color:#d1d5db;margin-top:8px;padding:0px;font-size:12px;")
        self.build_status.hide()
        self.builder = None
        self.worker = None

        self.make_config_widgets()

        self.console_toggle = QPushButton("Console output  ▲")
        self.console_toggle.clicked.connect(self.toggle_console)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(260)
        self.log.setMaximumHeight(420)
        self.console_empty = QLabel("No console output")
        self.console_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.console_empty.setMinimumHeight(260)
        self.console_stack = QWidget()
        self.console_stack_layout = QStackedLayout(self.console_stack)
        self.console_stack_layout.setContentsMargins(0, 0, 0, 0)
        self.console_stack_layout.addWidget(self.console_empty)
        self.console_stack_layout.addWidget(self.log)
        self.console_stack_layout.setCurrentWidget(self.console_empty)

        self.build()
        self.console_stack.hide()
        self.update_console_style(expanded=False)
        self.refresh()

    def make_config_widgets(self):
        self.image_size = QComboBox()
        self.image_size.setEditable(True)
        add_combo_items(self.image_size, ["16G", "32G", "64G", "128G"])
        self.auto_resize_label = "Use the full USB drive on first boot (auto-expand root filesystem)"
        self.auto_resize = QCheckBox()
        self.auto_resize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.auto_resize.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.auto_resize.setChecked(True)
        self.alpine_branch = QComboBox()
        self.alpine_branch.setEditable(True)
        add_combo_items(self.alpine_branch, ["latest-stable", "edge", "v3.22", "v3.21"])
        self.arch = QComboBox()
        add_combo_items(self.arch, ["x86_64"])
        self.hostname = QLineEdit("alpine-usb")
        self.username = QLineEdit("alpine")
        self.password = QLineEdit("")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Required")
        self.root_password = QLineEdit("")
        self.root_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.root_password.setPlaceholderText("Same as user password")
        self.root_password.setReadOnly(True)
        self.separate_root_password_label = "Use separate root password"
        self.separate_root_password = QCheckBox()
        self.separate_root_password.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.separate_root_password.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.show_passwords_label = "Show passwords"
        self.show_passwords = QCheckBox()
        self.show_passwords.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_passwords.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.show_passwords.stateChanged.connect(self.toggle_password_visibility)
        self.timezone = QComboBox()
        self.timezone.setEditable(True)
        add_combo_items(
            self.timezone,
            ["UTC", "America/Mexico_City", "America/Bogota", "America/Lima", "America/Santiago", "Europe/Madrid"],
        )
        self.locale = QComboBox()
        self.locale.setEditable(True)
        add_combo_items(self.locale, ["en_US.UTF-8", "es_ES.UTF-8", "es_MX.UTF-8"])
        self.console_keymap = QComboBox()
        self.console_keymap.setEditable(True)
        add_combo_items(self.console_keymap, ["us", "la-latin1", "es", "br-abnt2", "fr", "de"])
        self.xkb_layout = QComboBox()
        self.xkb_layout.setEditable(True)
        add_combo_items(
            self.xkb_layout,
            [
                ("US English", "us"),
                ("Latin American Spanish", "latam"),
                ("Spanish", "es"),
                ("Brazil ABNT2", "br"),
                ("French", "fr"),
                ("German", "de"),
            ],
        )
        self.xkb_variant = QLineEdit("")
        self.xkb_model = QLineEdit("pc105")

        self.desktop = QComboBox()
        add_combo_items(
            self.desktop,
            [
                ("XFCE (default)", "xfce"),
                ("GNOME", "gnome"),
                ("KDE Plasma", "plasma"),
                ("MATE", "mate"),
                ("LXQt", "lxqt"),
                ("No desktop / WM only", "none"),
            ],
        )
        self.display_manager = QComboBox()
        add_combo_items(
            self.display_manager,
            [
                ("Auto recommended", "auto"),
                ("LightDM", "lightdm"),
                ("SDDM", "sddm"),
                ("GDM", "gdm"),
                ("LXDM", "lxdm"),
                ("greetd + tuigreet", "greetd"),
                ("None / TTY", "none"),
            ],
        )
        self.default_session = QComboBox()
        add_combo_items(
            self.default_session,
            [
                ("Auto", "auto"),
                ("XFCE", "xfce"),
                ("GNOME", "gnome"),
                ("Plasma", "plasma"),
                ("MATE", "mate"),
                ("LXQt", "lxqt"),
                ("i3", "i3"),
                ("Sway", "sway"),
                ("Hyprland", "hyprland"),
                ("Awesome", "awesome"),
                ("bspwm", "bspwm"),
                ("Openbox", "openbox"),
                ("labwc", "labwc"),
                ("Shell only", "shell"),
            ],
        )
        self.wm_checks: dict[str, QCheckBox] = {}
        self.wm_labels: dict[str, str] = {}
        for key, label in [
            ("i3", "i3 (X11 tiling)"),
            ("sway", "Sway (Wayland tiling)"),
            ("hyprland", "Hyprland (Wayland tiling)"),
            ("awesome", "AwesomeWM"),
            ("bspwm", "bspwm"),
            ("openbox", "Openbox"),
            ("labwc", "labwc (Wayland)"),
        ]:
            self.wm_labels[key] = label
            self.wm_checks[key] = QCheckBox()
            self.wm_checks[key].setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.wm_checks[key].setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.browser = QComboBox()
        add_combo_items(
            self.browser,
            [("Firefox", "firefox"), ("Firefox ESR", "firefox-esr"), ("Chromium", "chromium"), ("None", "none")],
        )
        self.audio = QComboBox()
        add_combo_items(self.audio, [("PipeWire", "pipewire"), ("ALSA only", "alsa"), ("None", "none")])

        self.network = QComboBox()
        add_combo_items(self.network, [("NetworkManager", "networkmanager"), ("Classic / none", "none")])
        self.wifi_label = "Wi-Fi support (wpa_supplicant, wireless-regdb, NM Wi-Fi)"
        self.wifi = QCheckBox()
        self.wifi.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.wifi.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.wifi.setChecked(True)
        self.bluetooth_label = "Bluetooth support (bluez, blueman, firmware)"
        self.bluetooth = QCheckBox()
        self.bluetooth.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bluetooth.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.bluetooth.setChecked(True)

        self.bootloader = QComboBox()
        add_combo_items(
            self.bootloader, [("GRUB removable UEFI", "grub"), ("systemd-boot removable UEFI", "systemd-boot")]
        )
        self.kernel = QComboBox()
        add_combo_items(self.kernel, [("linux-lts", "lts"), ("linux-stable", "stable")])
        self.firmware = QComboBox()
        add_combo_items(self.firmware, [("Full linux-firmware (recommended)", "full"), ("linux-firmware-none", "none")])
        self.legacy_x11_drivers_label = "Broad legacy X11 video drivers (maximum hardware compatibility)"
        self.legacy_x11_drivers = QCheckBox()
        self.legacy_x11_drivers.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.legacy_x11_drivers.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.legacy_x11_drivers.setChecked(True)
        self.boot_timeout = QLineEdit("3")
        self.extra_packages = QLineEdit("")
        self.extra_packages.setPlaceholderText("Type package names separated by spaces; suggestions search as you type")
        self.package_search_worker = None
        self.package_search_timer = QTimer(self)
        self.package_search_timer.setSingleShot(True)
        self.package_search_timer.setInterval(500)
        self.package_search_timer.timeout.connect(self.search_packages)
        self.package_search_active_query = ""
        self.package_search_pending = False
        self.package_search_results = PackageSuggestionList()
        self.package_search_results.setMaximumHeight(150)
        self.package_search_results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.package_search_results.accept_suggestion.connect(self.add_selected_packages)
        self.package_search_status = QLabel("Type a package name for suggestions. ↓ selects, →/Enter accepts.")
        self.package_search_status.setStyleSheet("color:#cbd5e1;font-size:12px;")
        self.extra_packages.installEventFilter(self)
        self.extra_packages.textChanged.connect(self.schedule_package_search)
        self.package_search_results.itemDoubleClicked.connect(lambda _item: self.add_selected_packages())
        self.default_config = self.snapshot_config()
        self.saved_config_snapshot = dict(self.default_config)
        self.connect_config_change_signals()
        self.load_saved_config_if_available()

    def set_combo_value(self, combo: QComboBox, value: str):
        for i in range(combo.count()):
            data = combo.itemData(i)
            if str(data) == value or combo.itemText(i) == value:
                combo.setCurrentIndex(i)
                return
        if combo.isEditable():
            combo.setCurrentText(value)

    def snapshot_config(self) -> dict:
        return {
            "image": self.image.text(),
            "image_size": self.image_size.currentText(),
            "alpine_branch": self.alpine_branch.currentText(),
            "arch": combo_value(self.arch),
            "hostname": self.hostname.text(),
            "username": self.username.text(),
            "separate_root_password": self.separate_root_password.isChecked(),
            # Passwords are intentionally not persisted. They stay in memory for
            # the current app session and are read only when building an image.
            "timezone": self.timezone.currentText(),
            "locale": self.locale.currentText(),
            "console_keymap": self.console_keymap.currentText(),
            "xkb_layout": combo_value(self.xkb_layout),
            "xkb_variant": self.xkb_variant.text(),
            "xkb_model": self.xkb_model.text(),
            "desktop": combo_value(self.desktop),
            "display_manager": combo_value(self.display_manager),
            "default_session": combo_value(self.default_session),
            "browser": combo_value(self.browser),
            "audio": combo_value(self.audio),
            "network": combo_value(self.network),
            "wifi": self.wifi.isChecked(),
            "bluetooth": self.bluetooth.isChecked(),
            "bootloader": combo_value(self.bootloader),
            "kernel": combo_value(self.kernel),
            "firmware": combo_value(self.firmware),
            "legacy_x11_drivers": self.legacy_x11_drivers.isChecked(),
            "boot_timeout": self.boot_timeout.text(),
            "auto_resize": self.auto_resize.isChecked(),
            "extra_packages": self.extra_packages.text(),
            "wms": self.selected_wms(),
        }

    def apply_config(self, cfg: dict):
        self.image.setText(str(cfg.get("image", DEFAULT_OUTPUT_PATH)))
        self.image_size.setCurrentText(str(cfg.get("image_size", "16G")))
        self.alpine_branch.setCurrentText(str(cfg.get("alpine_branch", "latest-stable")))
        self.set_combo_value(self.arch, str(cfg.get("arch", "x86_64")))
        self.hostname.setText(str(cfg.get("hostname", "alpine-usb")))
        self.username.setText(str(cfg.get("username", "alpine")))
        self.separate_root_password.setChecked(bool(cfg.get("separate_root_password", False)))
        # Never load persisted passwords. Older config files may contain these
        # keys; load_saved_config_if_available() scrubs them from disk.
        self.timezone.setCurrentText(str(cfg.get("timezone", "UTC")))
        self.locale.setCurrentText(str(cfg.get("locale", "en_US.UTF-8")))
        self.console_keymap.setCurrentText(str(cfg.get("console_keymap", "us")))
        self.set_combo_value(self.xkb_layout, str(cfg.get("xkb_layout", "us")))
        self.xkb_variant.setText(str(cfg.get("xkb_variant", "")))
        self.xkb_model.setText(str(cfg.get("xkb_model", "pc105")))
        for key in [
            "desktop",
            "display_manager",
            "default_session",
            "browser",
            "audio",
            "network",
            "bootloader",
            "kernel",
            "firmware",
        ]:
            self.set_combo_value(getattr(self, key), str(cfg.get(key, combo_value(getattr(self, key)))))
        self.wifi.setChecked(bool(cfg.get("wifi", True)))
        self.bluetooth.setChecked(bool(cfg.get("bluetooth", True)))
        self.legacy_x11_drivers.setChecked(bool(cfg.get("legacy_x11_drivers", True)))
        self.boot_timeout.setText(str(cfg.get("boot_timeout", "3")))
        self.auto_resize.setChecked(bool(cfg.get("auto_resize", True)))
        self.extra_packages.setText(str(cfg.get("extra_packages", "")))
        selected = set(cfg.get("wms", []))
        for key, cb in self.wm_checks.items():
            cb.setChecked(key in selected)
        self.update_selected()
        self.update_dirty_indicators()

    def config_label(self, key: str, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color:#ffffff;border:0;background:transparent;")
        self.field_labels[key] = label
        self.field_label_text[key] = text
        return label

    def normalized_config_value(self, cfg: dict, key: str):
        if key.startswith("wm:"):
            wm = key.split(":", 1)[1]
            return wm in set(cfg.get("wms", []))
        if key == "wms":
            return sorted(cfg.get("wms", []))
        return cfg.get(key, self.default_config.get(key))

    def config_dirty(self, key: str, current: dict | None = None) -> bool:
        current = current or self.snapshot_config()
        saved = getattr(self, "saved_config_snapshot", self.default_config)
        return self.normalized_config_value(current, key) != self.normalized_config_value(saved, key)

    def section_dirty(self, keys: list[str], current: dict | None = None) -> bool:
        current = current or self.snapshot_config()
        return any(self.config_dirty(key, current) for key in keys)

    def update_required_field_highlights(self):
        if not hasattr(self, "password"):
            return
        required_empty_style = (
            "background:#450a0a;color:#ffffff;border:1px solid #ef4444;"
            "border-radius:4px;padding:2px 5px;min-height:24px;"
        )
        self.password.setStyleSheet(required_empty_style if not self.password.text().strip() else "")
        self.root_password.setStyleSheet(
            required_empty_style
            if self.separate_root_password.isChecked() and not self.root_password.text().strip()
            else ""
        )

    def update_dirty_indicators(self):
        if not hasattr(self, "field_labels"):
            return
        self.update_required_field_highlights()
        current = self.snapshot_config()
        for key, label in self.field_labels.items():
            dirty = self.config_dirty(key, current)
            base = self.field_label_text[key]
            label.setText(("● " if dirty else "") + base)
            label.setStyleSheet(("color:#fbbf24;" if dirty else "color:#ffffff;") + "border:0;background:transparent;")
        for name, keys in getattr(self, "section_fields", {}).items():
            section = self.sections.get(name)
            if section:
                section.set_dirty(self.section_dirty(keys, current))
        any_dirty = self.section_dirty(list(current.keys()), current)
        if hasattr(self, "img_title"):
            self.img_title.setText(self.image_title_base + ("  ●" if any_dirty else ""))
            self.img_title.setStyleSheet(
                "font-size:15px;font-weight:bold;margin:6px 0px 2px 0px;padding:0px;"
                + ("color:#fbbf24;" if any_dirty else "color:#93c5fd;")
            )
        if hasattr(self, "save_config_button"):
            self.save_config_button.setText(("● " if any_dirty else "") + "Save configuration")

    def write_saved_config(self, cfg: dict):
        SAVED_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        SAVED_CONFIG_PATH.write_text(json.dumps(cfg, indent=2, sort_keys=True))
        try:
            SAVED_CONFIG_PATH.chmod(0o600)
        except OSError:
            pass

    def load_saved_config_if_available(self):
        try:
            if SAVED_CONFIG_PATH.exists():
                cfg = json.loads(SAVED_CONFIG_PATH.read_text())
                scrubbed = dict(cfg)
                scrubbed.pop("password", None)
                scrubbed.pop("root_password", None)
                if scrubbed != cfg:
                    self.write_saved_config(scrubbed)
                self.saved_config_snapshot = dict(scrubbed)
                self.apply_config(scrubbed)
                self.password.clear()
                self.root_password.clear()
                self.sync_root_password_state()
        except Exception:
            pass

    def save_config(self):
        self.saved_config_snapshot = self.snapshot_config()
        self.write_saved_config(self.saved_config_snapshot)
        self.refresh_build_summary()
        self.update_dirty_indicators()
        modal(
            self,
            "info",
            APP_TITLE,
            f"Configuration saved:\n{SAVED_CONFIG_PATH}\n\nPasswords are not saved; enter them again after restarting the app.",
        )

    def restore_defaults(self):
        self.saved_config_snapshot = dict(self.default_config)
        self.apply_config(dict(self.default_config))
        self.password.clear()
        self.root_password.clear()
        self.sync_root_password_state()
        self.write_saved_config(self.saved_config_snapshot)
        self.refresh_build_summary()
        self.update_dirty_indicators()
        modal(self, "info", APP_TITLE, "Default image configuration restored. Passwords were not saved.")

    def connect_config_change_signals(self):
        def changed(*_args):
            # The summary shows saved image config; dirty dots show unsaved changes.
            self.update_selected()
            self.update_dirty_indicators()

        for widget in [
            self.image_size,
            self.alpine_branch,
            self.arch,
            self.timezone,
            self.locale,
            self.console_keymap,
            self.xkb_layout,
            self.desktop,
            self.display_manager,
            self.default_session,
            self.browser,
            self.audio,
            self.network,
            self.bootloader,
            self.kernel,
            self.firmware,
        ]:
            widget.currentTextChanged.connect(changed)
        for widget in [
            self.image,
            self.hostname,
            self.username,
            self.xkb_variant,
            self.xkb_model,
            self.boot_timeout,
            self.extra_packages,
        ]:
            widget.textChanged.connect(changed)

        def password_changed(*_args):
            self.sync_root_password_state()
            changed()

        self.password.textChanged.connect(password_changed)
        self.root_password.textChanged.connect(changed)
        self.separate_root_password.stateChanged.connect(lambda *_args: (self.sync_root_password_state(), changed()))
        for widget in [self.auto_resize, self.legacy_x11_drivers, self.wifi, self.bluetooth, *self.wm_checks.values()]:
            widget.stateChanged.connect(changed)

    def checkbox_row(self, checkbox: QCheckBox, text: str, key: str | None = None) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background:transparent;border:0;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = self.config_label(key, text) if key else QLabel(text)
        label.setStyleSheet("background:transparent;border:0;color:#ffffff;")
        label.mousePressEvent = lambda _event: checkbox.toggle()
        row.mousePressEvent = lambda _event: checkbox.toggle()
        layout.addWidget(checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return row

    def sync_root_password_state(self):
        if not hasattr(self, "separate_root_password"):
            return
        separate = self.separate_root_password.isChecked()
        if not separate and self.root_password.text() != self.password.text():
            self.root_password.setText(self.password.text())
        self.root_password.setReadOnly(not separate)
        self.root_password.setPlaceholderText("Required when separate" if separate else "Same as user password")
        self.root_password.setToolTip(
            "Enter a different root password" if separate else "Root password will match the user password"
        )
        self.update_required_field_highlights()

    def toggle_password_visibility(self):
        mode = QLineEdit.EchoMode.Normal if self.show_passwords.isChecked() else QLineEdit.EchoMode.Password
        self.password.setEchoMode(mode)
        self.root_password.setEchoMode(mode)

    def build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        self.setStyleSheet("""
            QWidget { background:#111827; color:#ffffff; }
            QLabel { color:#ffffff; margin:0px; padding:0px; border:0; background:transparent; }
            QFormLayout QLabel { border:0; background:transparent; }
            QLineEdit, QComboBox { background:#1f2937; color:#ffffff; border:0; border-radius:4px; padding:2px 5px; min-height:24px; }
            QLineEdit:read-only { background:#111827; color:#cbd5e1; border:1px solid #374151; }
            QComboBox QAbstractItemView { background:#1f2937; color:#ffffff; selection-background-color:#2563eb; }
            QCheckBox { color:#ffffff; spacing:8px; min-height:22px; border:0; background:transparent; padding:0px; }
            QTextEdit { background:#0b1220; color:#ffffff; border:1px solid #374151; border-radius:6px; }
            QPushButton { background:#2563eb; color:#ffffff; border:0; border-radius:6px; padding:3px 8px; min-height:24px; }
            QPushButton:hover { background:#1d4ed8; }
            QPushButton:disabled { background:#4b5563; color:#d1d5db; }
            QListWidget { background:#0b1220; color:#ffffff; border:1px solid #374151; }
            QProgressBar { color:#ffffff; }
            QScrollArea { border:0; }
            QAbstractScrollArea { background:#111827; }
            QScrollBar:vertical { background:#0f172a; width:12px; margin:2px 2px 2px 2px; border:0; border-radius:6px; }
            QScrollBar::handle:vertical { background:#475569; min-height:30px; border-radius:5px; }
            QScrollBar::handle:vertical:hover { background:#64748b; }
            QScrollBar::handle:vertical:pressed { background:#93c5fd; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; border:0; background:transparent; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
            QScrollBar:horizontal { background:#0f172a; height:12px; margin:2px 2px 2px 2px; border:0; border-radius:6px; }
            QScrollBar::handle:horizontal { background:#475569; min-width:30px; border-radius:5px; }
            QScrollBar::handle:horizontal:hover { background:#64748b; }
            QScrollBar::handle:horizontal:pressed { background:#93c5fd; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0px; border:0; background:transparent; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background:transparent; }
        """)
        title = QLabel("Alpine USB Installer")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#ffffff;margin:0px;padding:0px;")
        subtitle = QLabel("Build and flash a customizable preinstalled Alpine Linux USB image.")
        subtitle.setStyleSheet("color:#cbd5e1;margin:0px;padding:0px;font-size:12px;")
        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(3)
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.field_labels = {}
        self.field_label_text = {}
        self.sections = {}
        self.section_fields = {}
        self.image_title_base = "1. Image configuration"
        self.img_title = QLabel(self.image_title_base)
        self.img_title.setStyleSheet(
            "font-size:15px;font-weight:bold;color:#93c5fd;margin:6px 0px 2px 0px;padding:0px;"
        )
        content_layout.addWidget(self.img_title)
        img_grid = QGridLayout()
        img_grid.setColumnStretch(1, 1)
        img_grid.setHorizontalSpacing(10)
        img_grid.setVerticalSpacing(8)
        choose_output = QPushButton("Select path")
        choose_output.setIcon(make_button_icon("folder"))
        choose_output.clicked.connect(self.choose_output_path)
        choose_output.setFixedWidth(120)
        self.build_button = QPushButton("Build image")
        self.build_button.setIcon(make_button_icon("build"))
        self.build_button.clicked.connect(self.build_image)
        self.build_button.setFixedWidth(150)
        self.build_button.setStyleSheet(
            "background:#16a34a;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:24px;"
        )
        img_grid.addWidget(self.config_label("image", "Output path:"), 0, 0)
        img_grid.addWidget(self.image, 0, 1)
        img_grid.addWidget(choose_output, 0, 2)
        content_layout.addLayout(img_grid)

        config_note = QLabel("Configuration sections are collapsed by default; open only what you want to customize.")
        config_note.setStyleSheet("color:#cbd5e1;font-size:12px;margin-top:6px;")
        content_layout.addWidget(config_note)
        self.add_config_sections(content_layout)

        config_actions = QHBoxLayout()
        config_actions.setSpacing(8)
        self.save_config_button = QPushButton("Save configuration")
        self.save_config_button.setIcon(make_button_icon("check"))
        self.save_config_button.clicked.connect(self.save_config)
        self.restore_defaults_button = QPushButton("Restore defaults")
        self.restore_defaults_button.setIcon(make_button_icon("refresh"))
        self.restore_defaults_button.clicked.connect(self.restore_defaults)
        self.restore_defaults_button.setStyleSheet(
            "background:#16a34a;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:24px;"
        )
        config_actions.addWidget(self.save_config_button)
        config_actions.addWidget(self.restore_defaults_button)
        config_actions.addStretch(1)
        content_layout.addLayout(config_actions)
        self.update_dirty_indicators()

        build_title = QLabel("2. Image build")
        build_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:10px 0px 2px 0px;padding:0px;")
        content_layout.addWidget(build_title)
        build_box = QVBoxLayout()
        build_box.setSpacing(6)
        self.build_summary = QLabel("")
        self.build_summary.setWordWrap(True)
        self.build_summary.setTextFormat(Qt.TextFormat.RichText)
        self.build_summary.setStyleSheet(
            "color:#cbd5e1;font-size:12px;margin:0px 0px 6px 0px;padding:8px;background:#0f172a;border:1px solid #374151;border-radius:6px;"
        )
        build_box.addWidget(self.build_summary)
        self.refresh_build_summary()
        build_buttons = QHBoxLayout()
        build_buttons.addWidget(self.build_button)
        build_buttons.addStretch()
        build_box.addLayout(build_buttons)
        build_box.addWidget(self.build_status)
        self.build_progress = QProgressBar()
        self.build_progress.setRange(0, 0)
        self.build_progress.hide()
        build_box.addWidget(self.build_progress)
        content_layout.addLayout(build_box)

        usb_title = QLabel("3. USB target")
        usb_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:10px 0px 2px 0px;padding:0px;")
        content_layout.addWidget(usb_title)
        usb_box = QVBoxLayout()
        usb_box.setSpacing(6)
        usb_row = QHBoxLayout()
        usb_row.setSpacing(8)
        self.pick_button = QPushButton("Select USB")
        self.pick_button.setIcon(make_button_icon("usb"))
        self.pick_button.clicked.connect(self.pick)
        self.pick_button.setFixedWidth(150)
        self.flash_button = QPushButton("Flash USB")
        self.flash_button.setIcon(make_button_icon("flash"))
        self.flash_button.clicked.connect(self.flash)
        self.flash_button.setFixedWidth(150)
        self.flash_button.setEnabled(False)
        self.flash_button.setStyleSheet("""
            QPushButton { background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:24px; }
            QPushButton:disabled { background:#374151;color:#9ca3af; }
        """)
        device_label = QLabel("Device:")
        device_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        usb_row.addWidget(device_label)
        usb_row.addWidget(self.device, 1)
        usb_row.addWidget(self.pick_button)
        usb_box.addLayout(usb_row)
        flash_row = QHBoxLayout()
        flash_row.addWidget(self.flash_button)
        flash_row.addStretch()
        usb_box.addLayout(flash_row)
        warn = QLabel("⚠ Flashing permanently erases the selected USB device.")
        warn.setStyleSheet("color:#fca5a5;font-weight:bold;margin:0px;padding:0px;font-size:12px;")
        usb_box.addWidget(warn)
        usb_box.addWidget(self.status)
        self.flash_progress = QProgressBar()
        self.flash_progress.setRange(0, 100)
        self.flash_progress.setValue(0)
        self.flash_progress.hide()
        usb_box.addWidget(self.flash_progress)
        content_layout.addLayout(usb_box)
        self.device.textChanged.connect(self.update_selected)
        content_layout.addStretch(1)

        console_box = QVBoxLayout()
        console_box.setContentsMargins(0, 8, 0, 0)
        console_box.setSpacing(0)
        console_box.addWidget(self.console_toggle)
        console_box.addWidget(self.console_stack)
        layout.addLayout(console_box)

    def add_config_sections(self, parent_layout: QVBoxLayout):
        self.section_fields = {
            "system": [
                "image_size",
                "alpine_branch",
                "arch",
                "hostname",
                "username",
                "separate_root_password",
                "password",
                "root_password",
                "timezone",
                "locale",
                "console_keymap",
                "xkb_layout",
                "xkb_variant",
                "xkb_model",
            ],
            "desktop": ["desktop", "display_manager", "default_session", "browser", "audio", "wms"],
            "network": ["network", "wifi", "bluetooth"],
            "boot": ["bootloader", "kernel", "firmware", "legacy_x11_drivers", "boot_timeout", "auto_resize"],
            "extra": ["extra_packages"],
        }

        system = CollapsibleSection("System, user, localization (required)", collapsed=False)
        self.sections["system"] = system
        required_note = QLabel(
            "Required before build. By default, root password matches the user password. Enable separate root password only if you want different credentials. Passwords are not saved."
        )
        required_note.setWordWrap(True)
        required_note.setStyleSheet(
            "color:#fbbf24;font-size:12px;margin:2px 0px 8px 0px;padding:0px;border:0;background:transparent;"
        )
        system.body_layout.addWidget(required_note)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        for key, label, widget in [
            ("image_size", "Minimum image size:", self.image_size),
            ("alpine_branch", "Alpine branch:", self.alpine_branch),
            ("arch", "Architecture:", self.arch),
            ("hostname", "Hostname:", self.hostname),
            ("username", "User:", self.username),
            ("password", "User password *:", self.password),
            (
                "separate_root_password",
                "",
                self.checkbox_row(
                    self.separate_root_password, self.separate_root_password_label, "separate_root_password"
                ),
            ),
            ("root_password", "Root password:", self.root_password),
            ("show_passwords", "", self.checkbox_row(self.show_passwords, self.show_passwords_label)),
            ("timezone", "Timezone:", self.timezone),
            ("locale", "Locale:", self.locale),
            ("console_keymap", "Console keymap:", self.console_keymap),
            ("xkb_layout", "XKB layout:", self.xkb_layout),
            ("xkb_variant", "XKB variant:", self.xkb_variant),
            ("xkb_model", "XKB model:", self.xkb_model),
        ]:
            form.addRow(self.config_label(key, label) if label else QLabel(""), widget)
        system.body_layout.addLayout(form)
        parent_layout.addWidget(system)

        desktop = CollapsibleSection("Desktop environments, display manager and window managers", collapsed=True)
        self.sections["desktop"] = desktop
        dform = QFormLayout()
        dform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        dform.setHorizontalSpacing(12)
        dform.setVerticalSpacing(8)
        for key, label, widget in [
            ("desktop", "Desktop:", self.desktop),
            ("display_manager", "Display manager:", self.display_manager),
            ("default_session", "Default session:", self.default_session),
            ("browser", "Browser:", self.browser),
            ("audio", "Audio:", self.audio),
        ]:
            dform.addRow(self.config_label(key, label), widget)
        desktop.body_layout.addLayout(dform)
        wm_label = QLabel("Optional tiling/window managers:")
        wm_label.setStyleSheet("color:#cbd5e1;font-weight:bold;border:0;background:transparent;")
        desktop.body_layout.addWidget(wm_label)
        wm_grid = QGridLayout()
        wm_grid.setHorizontalSpacing(18)
        wm_grid.setVerticalSpacing(6)
        for i, (key, cb) in enumerate(self.wm_checks.items()):
            wm_grid.addWidget(self.checkbox_row(cb, self.wm_labels[key], f"wm:{key}"), i // 2, i % 2)
        desktop.body_layout.addLayout(wm_grid)
        parent_layout.addWidget(desktop)

        network = CollapsibleSection("Network, Wi‑Fi and Bluetooth", collapsed=True)
        self.sections["network"] = network
        nform = QFormLayout()
        nform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        nform.setHorizontalSpacing(12)
        nform.setVerticalSpacing(8)
        nform.addRow(self.config_label("network", "Network backend:"), self.network)
        nform.addRow(self.config_label("wifi", "Wi‑Fi:"), self.checkbox_row(self.wifi, self.wifi_label, "wifi"))
        nform.addRow(
            self.config_label("bluetooth", "Bluetooth:"),
            self.checkbox_row(self.bluetooth, self.bluetooth_label, "bluetooth"),
        )
        network.body_layout.addLayout(nform)
        parent_layout.addWidget(network)

        boot = CollapsibleSection("Bootloader, kernel and firmware", collapsed=True)
        self.sections["boot"] = boot
        bform = QFormLayout()
        bform.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        bform.setHorizontalSpacing(12)
        bform.setVerticalSpacing(8)
        for key, label, widget in [
            ("bootloader", "Bootloader:", self.bootloader),
            ("kernel", "Kernel:", self.kernel),
            ("firmware", "Firmware:", self.firmware),
            (
                "legacy_x11_drivers",
                "X11 drivers:",
                self.checkbox_row(self.legacy_x11_drivers, self.legacy_x11_drivers_label, "legacy_x11_drivers"),
            ),
            ("boot_timeout", "Boot menu timeout:", self.boot_timeout),
            ("auto_resize", "USB space:", self.checkbox_row(self.auto_resize, self.auto_resize_label, "auto_resize")),
        ]:
            bform.addRow(self.config_label(key, label), widget)
        boot.body_layout.addLayout(bform)
        parent_layout.addWidget(boot)

        extra = CollapsibleSection("Extra APK packages", collapsed=True)
        self.sections["extra"] = extra
        extra.body_layout.addWidget(
            QLabel(
                "Type package names separated by spaces. Suggestions search Alpine main/community after a short delay."
            )
        )
        extra.body_layout.addWidget(self.config_label("extra_packages", "Packages:"))
        extra.body_layout.addWidget(self.extra_packages)
        extra.body_layout.addWidget(self.package_search_results)
        extra.body_layout.addWidget(self.package_search_status)
        parent_layout.addWidget(extra)

    def current_package_query(self) -> str:
        text = self.extra_packages.text()
        if not text or text[-1].isspace():
            return ""
        return re.split(r"\s+", text.strip())[-1]

    def schedule_package_search(self):
        query = self.current_package_query()
        if len(query) < 2:
            self.package_search_timer.stop()
            self.package_search_results.clear()
            self.package_search_status.setText("Type at least 2 characters in the packages field for suggestions.")
            return
        self.package_search_status.setText(f"Will search suggestions for '{query}'…")
        self.package_search_timer.start()

    def eventFilter(self, obj, event):
        if obj is getattr(self, "extra_packages", None) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down and self.package_search_results.count():
                if self.package_search_results.currentRow() < 0:
                    self.package_search_results.setCurrentRow(0)
                self.package_search_results.setFocus()
                return True
            if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                at_end = self.extra_packages.cursorPosition() == len(self.extra_packages.text())
                if at_end and self.package_search_results.count():
                    self.add_selected_packages()
                    return True
        return super().eventFilter(obj, event)

    def search_packages(self):
        query = self.current_package_query()
        if len(query) < 2:
            self.package_search_status.setText("Type at least 2 characters in the packages field for suggestions.")
            self.package_search_results.clear()
            return
        if self.thread_running(self.package_search_worker):
            self.package_search_pending = True
            self.package_search_status.setText("Search running; queued latest text…")
            return
        branch = self.alpine_branch.currentText().strip() or "latest-stable"
        arch = combo_value(self.arch) or "x86_64"
        self.package_search_active_query = query
        self.package_search_results.clear()
        self.package_search_status.setText(f"Searching {branch}/{arch} main + community…")
        self.package_search_worker = ApkSearchWorker(branch, arch, query)
        self.package_search_worker.done.connect(self.package_search_done)
        self.package_search_worker.failed.connect(self.package_search_failed)
        self.package_search_worker.finished.connect(self.package_search_finished)
        self.package_search_worker.start()

    def package_search_done(self, query: str, results: list):
        if query != self.current_package_query():
            self.package_search_pending = True
            return
        self.package_search_results.clear()
        if not results:
            self.package_search_status.setText(f"No official packages found for '{query}'.")
            return
        for package in results:
            desc = package.get("description") or "No description"
            text = f"{package['name']} — {desc} [{package.get('repo', '?')}]"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, package["name"])
            self.package_search_results.addItem(item)
        self.package_search_results.setCurrentRow(0)
        first = self.package_search_results.item(0)
        if first:
            first.setSelected(True)
        self.package_search_status.setText(
            f"Top {len(results)} suggestions. ↓/↑ moves, →/Enter or double-click accepts."
        )

    def package_search_failed(self, query: str, message: str):
        self.package_search_results.clear()
        self.package_search_status.setText(f"Search failed for '{query}': {message}")

    def package_search_finished(self):
        if self.sender() is self.package_search_worker:
            self.package_search_worker = None
        if self.package_search_pending:
            self.package_search_pending = False
            if len(self.current_package_query()) >= 2:
                self.package_search_timer.start(100)
        self.update_selected()

    def add_selected_packages(self):
        items = self.package_search_results.selectedItems()
        if not items and self.package_search_results.currentItem():
            items = [self.package_search_results.currentItem()]
        names = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        names = [str(name) for name in names if name]
        if not names:
            self.package_search_status.setText("Select one or more suggestions first.")
            return
        text = self.extra_packages.text()
        trailing_space = bool(text and text[-1].isspace())
        tokens = [pkg for pkg in re.split(r"\s+", text.strip()) if pkg]
        query = self.current_package_query()
        if query and tokens and tokens[-1] == query and not trailing_space:
            tokens = tokens[:-1]
        existing_set = set(tokens)
        added = []
        for name in names:
            if name not in existing_set:
                tokens.append(name)
                existing_set.add(name)
                added.append(name)
        self.extra_packages.setText(" ".join(tokens) + (" " if tokens else ""))
        self.extra_packages.setCursorPosition(len(self.extra_packages.text()))
        self.package_search_results.clear()
        self.package_search_status.setText(
            "Added: " + ", ".join(added) if added else "Selected package(s) already added."
        )

    def update_console_style(self, expanded: bool):
        if expanded:
            self.console_toggle.setText("Console output  ▼")
            self.console_toggle.setStyleSheet(
                "text-align:left;font-size:15px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:5px 10px;background:#1f2937;"
                "border:1px solid #374151;border-bottom:0;"
                "border-top-left-radius:6px;border-top-right-radius:6px;"
                "border-bottom-left-radius:0px;border-bottom-right-radius:0px;"
            )
            panel_style = (
                "background:#0b1220;color:#ffffff;border:1px solid #374151;"
                "border-top:0;border-top-left-radius:0px;border-top-right-radius:0px;"
                "border-bottom-left-radius:6px;border-bottom-right-radius:6px;"
            )
            self.log.setStyleSheet(panel_style)
            self.console_stack.setStyleSheet(panel_style)
            self.console_empty.setStyleSheet("background:#0b1220;color:#ffffff;font-size:15pt;font-weight:bold;")
        else:
            self.console_toggle.setText("Console output  ▲")
            self.console_toggle.setStyleSheet(
                "text-align:left;font-size:15px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:5px 10px;background:#1f2937;"
                "border:1px solid #374151;border-radius:6px;"
            )

    def toggle_console(self):
        expanded = not self.console_stack.isVisible()
        self.console_stack.setVisible(expanded)
        self.update_console_style(expanded)

    def choose_output_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select output image path",
            self.image.text().strip() or str(DEFAULT_OUTPUT_PATH),
            "Disk images (*.img);;All files (*)",
        )
        if path:
            if not path.endswith(".img"):
                path += ".img"
            self.image.setText(path)

    def refresh(self):
        self.device.clear()
        self.status.clear()
        self.status.hide()
        self.build_status.clear()
        self.build_status.hide()
        self.build_progress.hide()
        self.flash_progress.hide()

    def pick(self):
        dlg = DeviceDialog(self)
        if dlg.exec() and dlg.selected:
            self.device.setText(dlg.selected)

    def update_selected(self):
        val = self.device.text().strip() or "none"
        self.setWindowTitle(f"{APP_TITLE} — {val}" if val != "none" else APP_TITLE)
        if not hasattr(self, "flash_button"):
            return
        if not self.has_running_worker():
            self.flash_button.setEnabled(bool(val != "none" and self.image.text().strip()))

    def thread_running(self, thread):
        return thread is not None and thread.isRunning()

    def has_running_worker(self):
        return (
            self.thread_running(self.builder)
            or self.thread_running(self.worker)
            or self.thread_running(self.package_search_worker)
        )

    def set_busy(self, busy: bool):
        widgets = [
            self.build_button,
            self.pick_button,
            self.device,
            self.image,
            self.image_size,
            self.alpine_branch,
            self.arch,
            self.hostname,
            self.username,
            self.password,
            self.root_password,
            self.timezone,
            self.locale,
            self.console_keymap,
            self.xkb_layout,
            self.xkb_variant,
            self.xkb_model,
            self.desktop,
            self.display_manager,
            self.default_session,
            self.browser,
            self.audio,
            self.network,
            self.wifi,
            self.bluetooth,
            self.bootloader,
            self.kernel,
            self.firmware,
            self.boot_timeout,
            self.auto_resize,
            self.extra_packages,
            self.package_search_results,
            self.save_config_button,
            self.restore_defaults_button,
            *self.wm_checks.values(),
        ]
        for widget in widgets:
            widget.setEnabled(not busy)
        self.flash_button.setEnabled(False if busy else bool(self.device.text().strip() and self.image.text().strip()))

    def selected_wms(self) -> list[str]:
        return [key for key, cb in self.wm_checks.items() if cb.isChecked()]

    def collect_build_env(self) -> dict[str, str]:
        password = self.password.text()
        root_password = self.root_password.text() if self.separate_root_password.isChecked() else password
        return {
            "IMAGE_NAME": DEFAULT_IMAGE_NAME,
            "IMAGE_SIZE": self.image_size.currentText().strip() or "16G",
            "ALPINE_BRANCH": self.alpine_branch.currentText().strip() or "latest-stable",
            "ARCH": combo_value(self.arch) or "x86_64",
            "ALPINE_USB_USER": self.username.text().strip() or "alpine",
            "ALPINE_USB_PASSWORD": password,
            "ALPINE_USB_ROOT_PASSWORD": root_password,
            "ALPINE_USB_HOSTNAME": self.hostname.text().strip() or "alpine-usb",
            "ALPINE_USB_TIMEZONE": self.timezone.currentText().strip() or "UTC",
            "ALPINE_USB_LOCALE": self.locale.currentText().strip() or "en_US.UTF-8",
            "ALPINE_USB_CONSOLE_KEYMAP": self.console_keymap.currentText().strip() or "us",
            "ALPINE_USB_XKB_LAYOUT": combo_value(self.xkb_layout) or "us",
            "ALPINE_USB_XKB_VARIANT": self.xkb_variant.text().strip(),
            "ALPINE_USB_XKB_MODEL": self.xkb_model.text().strip() or "pc105",
            "ALPINE_USB_DESKTOP": combo_value(self.desktop),
            "ALPINE_USB_TILING_WMS": " ".join(self.selected_wms()),
            "ALPINE_USB_DEFAULT_SESSION": combo_value(self.default_session),
            "ALPINE_USB_DISPLAY_MANAGER": combo_value(self.display_manager),
            "ALPINE_USB_NETWORK": combo_value(self.network),
            "ALPINE_USB_WIFI": "1" if self.wifi.isChecked() else "0",
            "ALPINE_USB_BLUETOOTH": "1" if self.bluetooth.isChecked() else "0",
            "ALPINE_USB_AUDIO": combo_value(self.audio),
            "ALPINE_USB_BROWSER": combo_value(self.browser),
            "ALPINE_USB_FIRMWARE": combo_value(self.firmware),
            "ALPINE_USB_LEGACY_X11_DRIVERS": "1" if self.legacy_x11_drivers.isChecked() else "0",
            "ALPINE_USB_BOOTLOADER": combo_value(self.bootloader),
            "ALPINE_USB_KERNEL_FLAVOR": combo_value(self.kernel),
            "ALPINE_USB_BOOT_TIMEOUT": self.boot_timeout.text().strip() or "3",
            "ALPINE_USB_AUTO_RESIZE": "1" if self.auto_resize.isChecked() else "0",
            "ALPINE_USB_EXTRA_PACKAGES": self.extra_packages.text().strip(),
        }

    def validate_build_config(self, env: dict[str, str]) -> str | None:
        size = env["IMAGE_SIZE"]
        if not re.match(r"^[0-9]+([KMGTP]?)$", size, re.I):
            return "Image size must look like 16G, 32768M, etc."
        if not BRANCH_RE.match(env["ALPINE_BRANCH"]):
            return "Alpine branch must be latest-stable, edge, or v<major>.<minor> (for example v3.22)."
        if not re.match(r"^[a-z_][a-z0-9_-]*$", env["ALPINE_USB_USER"]):
            return "Username must start with lowercase letter/_ and contain only lowercase letters, numbers, _ or -."
        if not env["ALPINE_USB_PASSWORD"]:
            return "User password cannot be empty."
        if self.separate_root_password.isChecked() and not env["ALPINE_USB_ROOT_PASSWORD"]:
            return "Root password cannot be empty when separate root password is enabled."
        package_error = validate_extra_packages(env["ALPINE_USB_EXTRA_PACKAGES"])
        if package_error:
            return package_error
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]$|^[A-Za-z0-9]$", env["ALPINE_USB_HOSTNAME"]):
            return "Hostname may contain only letters, numbers and dash; it cannot start/end with dash."
        if not env["ALPINE_USB_BOOT_TIMEOUT"].isdigit():
            return "Boot menu timeout must be a number."
        if (
            env["ALPINE_USB_DESKTOP"] == "none"
            and not env["ALPINE_USB_TILING_WMS"]
            and env["ALPINE_USB_DISPLAY_MANAGER"] not in {"auto", "none", "greetd"}
        ):
            return "Select a desktop/WM or use display manager Auto/None/greetd."
        session = env["ALPINE_USB_DEFAULT_SESSION"]
        if session == "auto":
            session = (
                env["ALPINE_USB_DESKTOP"]
                if env["ALPINE_USB_DESKTOP"] != "none"
                else (env["ALPINE_USB_TILING_WMS"].split() or ["shell"])[0]
            )
        if session in {"sway", "hyprland", "labwc"} and env["ALPINE_USB_DISPLAY_MANAGER"] in {"lightdm", "lxdm"}:
            return "Wayland sessions (Sway/Hyprland/labwc) need Auto, greetd, SDDM, GDM or no display manager; LightDM/LXDM are X11-only here."
        return None

    def config_summary_text(self, env: dict[str, str]) -> str:
        return (
            f"Image: {env['IMAGE_SIZE']} | Alpine: {env['ALPINE_BRANCH']} | Arch: {env['ARCH']}\n"
            f"System: hostname={env['ALPINE_USB_HOSTNAME']} | user={env['ALPINE_USB_USER']} | passwords hidden\n"
            f"Locale: {env['ALPINE_USB_LOCALE']} | TZ: {env['ALPINE_USB_TIMEZONE']} | console={env['ALPINE_USB_CONSOLE_KEYMAP']} | xkb={env['ALPINE_USB_XKB_LAYOUT']} {env['ALPINE_USB_XKB_VARIANT'] or ''} model={env['ALPINE_USB_XKB_MODEL']}\n"
            f"Desktop: {env['ALPINE_USB_DESKTOP']} | DM: {env['ALPINE_USB_DISPLAY_MANAGER']} | Session: {env['ALPINE_USB_DEFAULT_SESSION']} | WMs: {env['ALPINE_USB_TILING_WMS'] or 'none'}\n"
            f"Apps: browser={env['ALPINE_USB_BROWSER']} | audio={env['ALPINE_USB_AUDIO']}\n"
            f"Hardware/network: network={env['ALPINE_USB_NETWORK']} | Wi‑Fi={env['ALPINE_USB_WIFI']} | Bluetooth={env['ALPINE_USB_BLUETOOTH']}\n"
            f"Boot: {env['ALPINE_USB_BOOTLOADER']} | linux-{env['ALPINE_USB_KERNEL_FLAVOR']} | firmware={env['ALPINE_USB_FIRMWARE']} | legacy-X11={env.get('ALPINE_USB_LEGACY_X11_DRIVERS', '1')} | timeout={env['ALPINE_USB_BOOT_TIMEOUT']} | auto-resize={env['ALPINE_USB_AUTO_RESIZE']}\n"
            f"Extra packages: {env['ALPINE_USB_EXTRA_PACKAGES'] or 'none'}"
        )

    def summary_env_from_config(self, cfg: dict) -> dict[str, str]:
        return {
            "image": str(cfg.get("image", DEFAULT_OUTPUT_PATH)),
            "image_size": str(cfg.get("image_size", "16G")),
            "alpine_branch": str(cfg.get("alpine_branch", "latest-stable")),
            "arch": str(cfg.get("arch", "x86_64")),
            "hostname": str(cfg.get("hostname", "alpine-usb")),
            "username": str(cfg.get("username", "alpine")),
            "timezone": str(cfg.get("timezone", "UTC")),
            "locale": str(cfg.get("locale", "en_US.UTF-8")),
            "console_keymap": str(cfg.get("console_keymap", "us")),
            "xkb_layout": str(cfg.get("xkb_layout", "us")),
            "xkb_variant": str(cfg.get("xkb_variant", "")),
            "xkb_model": str(cfg.get("xkb_model", "pc105")),
            "desktop": str(cfg.get("desktop", "xfce")),
            "display_manager": str(cfg.get("display_manager", "auto")),
            "default_session": str(cfg.get("default_session", "auto")),
            "wms": " ".join(cfg.get("wms", [])),
            "browser": str(cfg.get("browser", "firefox")),
            "audio": str(cfg.get("audio", "pipewire")),
            "network": str(cfg.get("network", "networkmanager")),
            "wifi": "1" if cfg.get("wifi", True) else "0",
            "bluetooth": "1" if cfg.get("bluetooth", True) else "0",
            "bootloader": str(cfg.get("bootloader", "grub")),
            "kernel": str(cfg.get("kernel", "lts")),
            "firmware": str(cfg.get("firmware", "full")),
            "legacy_x11_drivers": "1" if cfg.get("legacy_x11_drivers", True) else "0",
            "boot_timeout": str(cfg.get("boot_timeout", "3")),
            "auto_resize": "1" if cfg.get("auto_resize", True) else "0",
            "extra_packages": str(cfg.get("extra_packages", "")),
        }

    def refresh_build_summary(self):
        if not hasattr(self, "build_summary"):
            return
        env = self.summary_env_from_config(getattr(self, "saved_config_snapshot", self.snapshot_config()))
        e = {key: html.escape(str(value)) for key, value in env.items()}
        extra = e.get("extra_packages", "").strip() or "none"
        wms = e.get("wms", "").strip() or "none"
        self.build_summary.setText(
            "<b>Saved image configuration</b><br>"
            f"<b>Output:</b> {e['image']}<br>"
            f"<b>Image:</b> size {e['image_size']} · Alpine {e['alpine_branch']} · arch {e['arch']}<br>"
            f"<b>System:</b> hostname {e['hostname']} · user {e['username']} · passwords hidden<br>"
            f"<b>Locale:</b> {e['locale']} · timezone {e['timezone']} · console keymap {e['console_keymap']} · XKB {e['xkb_layout']} · variant {e['xkb_variant'] or 'none'} · model {e['xkb_model']}<br>"
            f"<b>Desktop:</b> {e['desktop']} · display manager {e['display_manager']} · session {e['default_session']} · WMs {wms}<br>"
            f"<b>Apps/audio:</b> browser {e['browser']} · audio {e['audio']}<br>"
            f"<b>Network/hardware:</b> backend {e['network']} · Wi‑Fi {e['wifi']} · Bluetooth {e['bluetooth']}<br>"
            f"<b>Boot:</b> {e['bootloader']} · linux-{e['kernel']} · firmware {e['firmware']} · legacy-X11 {e['legacy_x11_drivers']} · timeout {e['boot_timeout']} · auto-resize {e['auto_resize']}<br>"
            f"<b>Extra packages:</b> {extra}"
        )

    def build_image(self):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "Another operation is still running. Wait for it to finish.")
            return
        output_path = self.image.text().strip() or str(DEFAULT_OUTPUT_PATH)
        Path(output_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        env = self.collect_build_env()
        validation_error = self.validate_build_config(env)
        if validation_error:
            modal(self, "error", APP_TITLE, validation_error)
            return
        if platform.system() == "Darwin":
            docker = find_executable("docker")
            if not docker:
                modal(
                    self,
                    "error",
                    APP_TITLE,
                    "Docker not found. Install Docker Desktop and try again. If it is installed, open Docker Desktop once so /usr/local/bin/docker is created.",
                )
                return
            if subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                modal(self, "error", APP_TITLE, "Docker is not running. Start Docker Desktop and try again.")
                return
        confirm = f"Build Alpine image?\n\nOutput:\n{output_path}\n\n{self.config_summary_text(env)}"
        if not modal(self, "question", APP_TITLE, confirm, question=True):
            return
        self.build_progress.show()
        self.flash_progress.hide()
        self.build_status.show()
        self.build_status.setText("Building image...")
        self.status.hide()
        self.set_busy(True)
        self.builder = BuildWorker(env, output_path)
        self.builder.log.connect(self.append_log)
        self.builder.done.connect(self.build_done)
        self.builder.finished.connect(self.build_thread_finished)
        self.builder.start()

    def build_done(self, ok, msg):
        self.build_progress.hide()
        self.build_status.show()
        self.build_status.setText(msg)
        self.status.hide()
        self.append_log(msg)
        if ok:
            m = re.search(r"Image build complete: (.+)$", msg)
            if m:
                self.image.setText(m.group(1))
        self.set_busy(False)
        modal(self, "info" if ok else "error", APP_TITLE, msg)

    def build_thread_finished(self):
        if self.sender() is self.builder:
            self.builder = None

    def flash(self):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "Another operation is still running. Wait for it to finish.")
            return
        img = self.image.text().strip()
        dev = self.device.text().strip()
        if not Path(img).exists():
            modal(self, "error", APP_TITLE, "Image not found.")
            return
        if not dev:
            modal(self, "error", APP_TITLE, "Select USB device.")
            return
        ok_safe, safe_dev, device_rows, reason = device_safety_report(dev)
        if not ok_safe:
            modal(self, "error", APP_TITLE, reason or "Unsafe USB target.")
            return
        device_details = "\n".join(f"{key}: {value}" for key, value in device_rows)
        if not modal(
            self,
            "question",
            APP_TITLE,
            f"Erase and flash this device?\n\n{device_details}\n\nImage: {img}\n\nThis permanently erases the selected USB device.",
            question=True,
        ):
            return
        dev = safe_dev
        sudo_password = None
        if platform.system() == "Darwin":
            sudo_password, ok = QInputDialog.getText(
                self,
                APP_TITLE,
                "Administrator password for flashing:",
                QLineEdit.EchoMode.Password,
            )
            if not ok or not sudo_password:
                return
        self.build_progress.hide()
        self.flash_progress.setRange(0, 100)
        self.flash_progress.setValue(0)
        self.flash_progress.show()
        self.status.show()
        self.status.setText("Flashing... 0%")
        self.set_busy(True)
        self.worker = FlashWorker(img, dev, sudo_password)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.update_flash_progress)
        self.worker.done.connect(self.flash_done)
        self.worker.finished.connect(self.flash_thread_finished)
        self.worker.start()

    def update_flash_progress(self, text):
        self.status.setText(text)
        m = re.search(r"Flashing\.\.\.\s*(\d+)%", text)
        if m:
            self.flash_progress.setValue(int(m.group(1)))

    def append_log(self, line):
        if self.console_stack_layout.currentWidget() is not self.log:
            self.console_stack_layout.setCurrentWidget(self.log)
        self.log.append(line)
        if self.log.document().blockCount() > 300:
            cursor = self.log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def flash_done(self, ok, msg):
        if ok:
            self.flash_progress.setValue(100)
        self.flash_progress.hide()
        self.status.show()
        self.status.setText(msg)
        self.append_log(msg)
        if ok:
            # USB is ejected; require explicit re-selection before another flash.
            self.device.clear()
        self.set_busy(False)
        # Let progress/status layout settle, then center completion modal over main window.
        QTimer.singleShot(0, lambda: modal(self, "info" if ok else "error", APP_TITLE, msg))

    def flash_thread_finished(self):
        if self.sender() is self.worker:
            self.worker = None

    def closeEvent(self, event):
        if self.has_running_worker():
            modal(
                self, "error", APP_TITLE, "An operation is still running. Wait for it to finish before closing the app."
            )
            event.ignore()
            return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setWindowIcon(make_app_icon())
    w = Main()
    w.show()
    QTimer.singleShot(0, lambda: ensure_widget_visible(w))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
