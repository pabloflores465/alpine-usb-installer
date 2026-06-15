#!/usr/bin/env python3
from __future__ import annotations

import io, os, platform, plistlib, re, shutil, subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

def prepare_frozen_runtime(bundle_dir: Path) -> Path:
    """Copy bundled build resources to a writable, stable directory.

    PyInstaller app bundles keep data files inside the .app internals. Docker
    Desktop can fail to mount those paths reliably, and the build scripts also
    create work files next to themselves. Use /tmp/alpine-usb-installer/app-runtime
    instead and make sure required files/directories exist there.
    """
    runtime = Path(tempfile.gettempdir()) / "alpine-usb-installer" / "app-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    for name in ["build-alpine-usb.sh", "configure-alpine-usb.sh", "README.md", "LICENSE"]:
        src = bundle_dir / name
        if src.exists():
            dst = runtime / name
            shutil.copy2(src, dst)
            if name.endswith(".sh"):
                dst.chmod(0o755)
    src_efi = bundle_dir / "efi-fallback"
    dst_efi = runtime / "efi-fallback"
    if src_efi.exists():
        if dst_efi.exists():
            shutil.rmtree(dst_efi)
        shutil.copytree(src_efi, dst_efi)
    (runtime / ".work").mkdir(exist_ok=True)
    return runtime


if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    SCRIPT_DIR = prepare_frozen_runtime(BUNDLE_DIR)
else:
    SCRIPT_DIR = Path(__file__).resolve().parent
    QT_VENV_PYTHON = SCRIPT_DIR / ".qtvenv" / "bin" / "python"
    if Path(sys.executable).resolve() != QT_VENV_PYTHON.resolve():
        if not QT_VENV_PYTHON.exists():
            subprocess.check_call([sys.executable, "-m", "venv", str(SCRIPT_DIR / ".qtvenv")])
            subprocess.check_call([str(QT_VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
            subprocess.check_call([str(QT_VENV_PYTHON), "-m", "pip", "install", "PySide6"])
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

from PySide6.QtCore import QPoint, Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QProgressBar,
    QScrollArea, QStackedLayout, QTextEdit, QVBoxLayout, QWidget
)

APP_TITLE = "Alpine USB Installer"
DEFAULT_IMAGE_NAME = "alpine-usb.img"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "alpine-usb-installer"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / DEFAULT_IMAGE_NAME


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
        p.drawPolyline(pts([(xy(3), xy(7)), (xy(3), xy(16)), (xy(17), xy(16)), (xy(17), xy(6)), (xy(9), xy(6)), (xy(7), xy(4)), (xy(3), xy(4)), (xy(3), xy(7))]))
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
        p.drawPolyline(pts([(xy(11), xy(2)), (xy(5), xy(11)), (xy(10), xy(11)), (xy(8), xy(18)), (xy(15), xy(8)), (xy(10), xy(8)), (xy(11), xy(2))]))
    elif kind == "refresh":
        p.drawArc(xy(5), xy(5), xy(10), xy(10), 35 * 16, 285 * 16)
        p.drawLine(xy(14), xy(5), xy(14), xy(9))
        p.drawLine(xy(14), xy(5), xy(10), xy(5))
    elif kind == "check":
        p.drawLine(xy(4), xy(10), xy(8), xy(15)); p.drawLine(xy(8), xy(15), xy(16), xy(5))
    elif kind == "warn":
        p.drawPolyline(pts([(xy(10), xy(3)), (xy(18), xy(17)), (xy(2), xy(17)), (xy(10), xy(3))])); p.drawLine(xy(10), xy(7), xy(10), xy(12)); p.drawPoint(xy(10), xy(15))
    elif kind == "error":
        p.drawEllipse(xy(3), xy(3), xy(14), xy(14)); p.drawLine(xy(7), xy(7), xy(13), xy(13)); p.drawLine(xy(13), xy(7), xy(7), xy(13))
    p.end()
    return QIcon(pix)


def ensure_widget_visible(widget: QWidget, parent: QWidget | None = None):
    screen = (parent.screen() if parent and parent.screen() else None) or widget.screen() or QApplication.primaryScreen()
    if not screen:
        return
    available = screen.availableGeometry()
    frame = widget.frameGeometry()
    if frame.width() <= 0 or frame.height() <= 0:
        widget.adjustSize()
        frame = widget.frameGeometry()
    if parent and parent.isVisible():
        frame.moveCenter(parent.frameGeometry().center())
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
    QTimer.singleShot(0, lambda: ensure_widget_visible(box, parent))
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
        cancel.setStyleSheet("background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
        ok.setStyleSheet("background:#2563eb;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
        exec_centered_dialog(box, parent)
        return box.clickedButton() == ok
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok = box.button(QMessageBox.StandardButton.Ok)
    if ok:
        ok.setIcon(make_button_icon("check"))
        ok.setStyleSheet("background:#2563eb;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
    exec_centered_dialog(box, parent)
    return True


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


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
    for item in items:
        if isinstance(item, tuple):
            combo.addItem(item[0], item[1])
        else:
            combo.addItem(item)


APK_MIRROR = "https://dl-cdn.alpinelinux.org/alpine"
APK_SEARCH_REPOS = ("main", "community")
APK_INDEX_CACHE: dict[tuple[str, str], list[dict[str, str]]] = {}


def parse_apkindex(text: str, repo: str) -> list[dict[str, str]]:
    packages = []
    current: dict[str, str] = {}
    for line in text.splitlines() + [""]:
        if not line:
            name = current.get("P")
            if name:
                packages.append({
                    "name": name,
                    "description": current.get("T", ""),
                    "version": current.get("V", ""),
                    "repo": repo,
                })
            current = {}
            continue
        if len(line) > 2 and line[1] == ":":
            current[line[0]] = line[2:]
    return packages


def fetch_official_apk_packages(branch: str, arch: str) -> list[dict[str, str]]:
    key = (branch, arch)
    if key in APK_INDEX_CACHE:
        return APK_INDEX_CACHE[key]

    merged: dict[str, dict[str, str]] = {}
    for repo in APK_SEARCH_REPOS:
        url = f"{APK_MIRROR}/{branch}/{repo}/{arch}/APKINDEX.tar.gz"
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = next((m for m in tar.getmembers() if m.name.endswith("APKINDEX")), None)
            if member is None:
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            text = fh.read().decode("utf-8", errors="replace")
        for package in parse_apkindex(text, repo):
            # Keep main over community if a name ever appears in both repos.
            merged.setdefault(package["name"], package)

    packages = sorted(merged.values(), key=lambda item: item["name"])
    APK_INDEX_CACHE[key] = packages
    return packages


def search_official_apk_packages(branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_apk_packages(branch, arch):
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        haystack = f"{name} {desc}"
        if not all(term in haystack for term in terms):
            continue
        if name == query:
            score = 0
        elif name.startswith(query):
            score = 1
        elif all(term in name for term in terms):
            score = 2
        else:
            score = 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]


def list_devices():
    sysname = platform.system()
    devices = []
    if sysname == "Darwin":
        cp = run(["diskutil", "list", "-plist", "external", "physical"])
        try:
            data = plistlib.loads(cp.stdout.encode())
            for disk in data.get("AllDisksAndPartitions", []):
                ident = disk.get("DeviceIdentifier")
                if not ident:
                    continue
                dev = f"/dev/{ident}"
                info = run(["diskutil", "info", "-plist", dev])
                label = dev
                try:
                    meta = plistlib.loads(info.stdout.encode())
                    size_bytes = int(meta.get("TotalSize", 0) or 0)
                    size = f"{size_bytes / 1_000_000_000:.1f} GB" if size_bytes else "unknown size"
                    media = meta.get("IORegistryEntryName") or meta.get("MediaName") or "USB"
                    volumes = []
                    for part in disk.get("Partitions", []) or []:
                        vol = part.get("VolumeName")
                        part_id = part.get("DeviceIdentifier")
                        if not vol and part_id:
                            part_info = run(["diskutil", "info", "-plist", f"/dev/{part_id}"])
                            try:
                                part_meta = plistlib.loads(part_info.stdout.encode())
                                vol = (
                                    part_meta.get("VolumeName")
                                    or part_meta.get("MediaName")
                                    or part_meta.get("MountPoint", "").rstrip("/").split("/")[-1]
                                )
                            except Exception:
                                pass
                        content = part.get("Content")
                        if vol and vol not in volumes:
                            volumes.append(vol)
                        elif content and content not in {"EFI", "Apple_partition_scheme"} and content not in volumes:
                            volumes.append(content)
                    vol_text = f" — Volume: {', '.join(volumes)}" if volumes else ""
                    label = f"{dev} ({size}) {media}{vol_text}"
                except Exception:
                    pass
                devices.append((dev, label))
        except Exception:
            pass
    elif sysname == "Linux":
        cp = run(["lsblk", "-dpno", "NAME,SIZE,TRAN,TYPE,MODEL"])
        for line in cp.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4 and parts[3] == "disk":
                name, size, tran = parts[0], parts[1], parts[2]
                model = parts[4] if len(parts) > 4 else ""
                if tran in {"usb", "mmc"} or name.startswith("/dev/sd"):
                    devices.append((name, f"{name} ({size}) {model}".strip()))
    return devices


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
        self.empty_usb_message.setStyleSheet("background:#0b1220;color:#ffffff;border:1px solid #374151;font-size:15pt;font-weight:bold;")
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
        self.cancel.setStyleSheet("background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
        btns.addWidget(self.use); btns.addWidget(self.refresh); btns.addStretch(); btns.addWidget(self.cancel)
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
            for _, label in self.devices:
                self.list.addItem(label)
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
        self.toggle.setText(f"{self.title}  {'▼' if expanded else '▲'}")
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
            env.update({k: str(v) for k, v in self.config_env.items()})
            env.setdefault("IMAGE_NAME", DEFAULT_IMAGE_NAME)
            script = SCRIPT_DIR / "build-alpine-usb.sh"
            if not script.exists():
                raise RuntimeError(f"Build script not found: {script}")
            script.chmod(0o755)
            configure = SCRIPT_DIR / "configure-alpine-usb.sh"
            if configure.exists():
                configure.chmod(0o755)
            cmd = [str(script)]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=str(SCRIPT_DIR))
            for line in proc.stdout or []:
                self.log.emit(line.rstrip())
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"Build failed with exit code {code}")
            built = str(Path.cwd() / env.get("IMAGE_NAME", DEFAULT_IMAGE_NAME))
            final = str(Path(self.output_path).expanduser())
            if final != built:
                Path(final).parent.mkdir(parents=True, exist_ok=True)
                if os.path.exists(final):
                    os.remove(final)
                shutil.move(built, final)
            self.done.emit(True, f"Image build complete: {final}")
        except Exception as e:
            self.done.emit(False, str(e))


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
            if platform.system() == "Darwin":
                raw = dev.replace("/dev/disk", "/dev/rdisk")
                tmp_image = os.path.join(tempfile.gettempdir(), DEFAULT_IMAGE_NAME)
                try: os.remove(tmp_image)
                except FileNotFoundError: pass
                try:
                    os.link(self.image, tmp_image)
                except OSError:
                    shutil.copyfile(self.image, tmp_image)
                log_path = os.path.join(tempfile.gettempdir(), "alpine-usb-flash.log")
                try: os.remove(log_path)
                except FileNotFoundError: pass
                total = os.path.getsize(tmp_image)
                if not self.sudo_password:
                    raise RuntimeError("Administrator password is required to flash the USB.")
                with open(log_path, "w") as log:
                    log.write("Alpine USB Installer - Flash USB\n")
                    log.write(f"Target: {dev}\nImage: {tmp_image}\n\n")
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
                        f"/bin/dd if={sh_quote(tmp_image)} of={sh_quote(raw)} bs=4m & "
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
                    self.progress.emit("Flashing... 0%")
                    while proc.poll() is None:
                        pos, last_percent = self.tail_progress(log_path, pos, total, last_percent)
                        self.msleep(500)
                    log.flush()
                    pos, last_percent = self.tail_progress(log_path, pos, total, last_percent)
                    if proc.returncode:
                        raise RuntimeError(f"Flashing failed with exit code {proc.returncode}")
                    subprocess.run(["sync"])
                    subprocess.run(["diskutil", "eject", dev], stdout=log, stderr=subprocess.STDOUT, text=True)
                self.done.emit(True, "DONE. USB flashed and ejected.")
            elif platform.system() == "Linux":
                cmd = ["dd", f"if={self.image}", f"of={dev}", "bs=4M", "status=progress", "conv=fsync"]
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

    def tail_progress(self, log_path: str, pos: int, total: int, last_percent: int):
        if not os.path.exists(log_path):
            return pos, last_percent
        with open(log_path, "r", errors="ignore") as fh:
            fh.seek(pos)
            data = fh.read()
            pos = fh.tell()
        for line in data.splitlines():
            self.log.emit(line)
            m = re.search(r"(\d+) bytes", line)
            if m and total:
                percent = min(100, int(int(m.group(1)) * 100 / total))
                if percent != last_percent:
                    self.progress.emit(f"Flashing... {percent}% ({m.group(1)} bytes)")
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
        self.log = QTextEdit(); self.log.setReadOnly(True)
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
        self.image_size = QComboBox(); self.image_size.setEditable(True)
        add_combo_items(self.image_size, ["16G", "32G", "64G", "128G"])
        self.auto_resize_label = "Use the full USB drive on first boot (auto-expand root filesystem)"
        self.auto_resize = QCheckBox()
        self.auto_resize.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.auto_resize.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.auto_resize.setChecked(True)
        self.alpine_branch = QComboBox(); self.alpine_branch.setEditable(True)
        add_combo_items(self.alpine_branch, ["latest-stable", "edge", "v3.22", "v3.21"])
        self.arch = QComboBox(); add_combo_items(self.arch, ["x86_64"])
        self.hostname = QLineEdit("alpine-usb")
        self.username = QLineEdit("alpine")
        self.password = QLineEdit("alpine"); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.root_password = QLineEdit("alpine"); self.root_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_passwords_label = "Show passwords"
        self.show_passwords = QCheckBox()
        self.show_passwords.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_passwords.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.show_passwords.stateChanged.connect(self.toggle_password_visibility)
        self.timezone = QComboBox(); self.timezone.setEditable(True)
        add_combo_items(self.timezone, ["UTC", "America/Mexico_City", "America/Bogota", "America/Lima", "America/Santiago", "Europe/Madrid"])
        self.locale = QComboBox(); self.locale.setEditable(True)
        add_combo_items(self.locale, ["en_US.UTF-8", "es_ES.UTF-8", "es_MX.UTF-8"])
        self.console_keymap = QComboBox(); self.console_keymap.setEditable(True)
        add_combo_items(self.console_keymap, ["us", "la-latin1", "es", "br-abnt2", "fr", "de"])
        self.xkb_layout = QComboBox(); self.xkb_layout.setEditable(True)
        add_combo_items(self.xkb_layout, [("US English", "us"), ("Latin American Spanish", "latam"), ("Spanish", "es"), ("Brazil ABNT2", "br"), ("French", "fr"), ("German", "de")])
        self.xkb_variant = QLineEdit("")
        self.xkb_model = QLineEdit("pc105")

        self.desktop = QComboBox()
        add_combo_items(self.desktop, [
            ("XFCE (default)", "xfce"), ("GNOME", "gnome"), ("KDE Plasma", "plasma"),
            ("MATE", "mate"), ("LXQt", "lxqt"), ("No desktop / WM only", "none"),
        ])
        self.display_manager = QComboBox()
        add_combo_items(self.display_manager, [
            ("Auto recommended", "auto"), ("LightDM", "lightdm"), ("SDDM", "sddm"),
            ("GDM", "gdm"), ("LXDM", "lxdm"), ("greetd + tuigreet", "greetd"), ("None / TTY", "none"),
        ])
        self.default_session = QComboBox()
        add_combo_items(self.default_session, [
            ("Auto", "auto"), ("XFCE", "xfce"), ("GNOME", "gnome"), ("Plasma", "plasma"),
            ("MATE", "mate"), ("LXQt", "lxqt"), ("i3", "i3"), ("Sway", "sway"),
            ("Hyprland", "hyprland"), ("Awesome", "awesome"), ("bspwm", "bspwm"),
            ("Openbox", "openbox"), ("labwc", "labwc"), ("Shell only", "shell"),
        ])
        self.wm_checks: dict[str, QCheckBox] = {}
        self.wm_labels: dict[str, str] = {}
        for key, label in [
            ("i3", "i3 (X11 tiling)"), ("sway", "Sway (Wayland tiling)"),
            ("hyprland", "Hyprland (Wayland tiling)"), ("awesome", "AwesomeWM"),
            ("bspwm", "bspwm"), ("openbox", "Openbox"), ("labwc", "labwc (Wayland)"),
        ]:
            self.wm_labels[key] = label
            self.wm_checks[key] = QCheckBox()
            self.wm_checks[key].setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.wm_checks[key].setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.browser = QComboBox(); add_combo_items(self.browser, [("Firefox ESR", "firefox-esr"), ("Firefox", "firefox"), ("Chromium", "chromium"), ("None", "none")])
        self.audio = QComboBox(); add_combo_items(self.audio, [("PipeWire", "pipewire"), ("ALSA only", "alsa"), ("None", "none")])

        self.network = QComboBox(); add_combo_items(self.network, [("NetworkManager", "networkmanager"), ("Classic / none", "none")])
        self.wifi_label = "Wi-Fi support (wpa_supplicant, wireless-regdb, NM Wi-Fi)"
        self.wifi = QCheckBox(); self.wifi.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.wifi.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False); self.wifi.setChecked(True)
        self.bluetooth_label = "Bluetooth support (bluez, blueman, firmware)"
        self.bluetooth = QCheckBox(); self.bluetooth.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.bluetooth.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False); self.bluetooth.setChecked(True)

        self.bootloader = QComboBox(); add_combo_items(self.bootloader, [("GRUB removable UEFI", "grub"), ("systemd-boot removable UEFI", "systemd-boot")])
        self.kernel = QComboBox(); add_combo_items(self.kernel, [("linux-lts", "lts"), ("linux-stable", "stable")])
        self.firmware = QComboBox(); add_combo_items(self.firmware, [("Full linux-firmware (recommended)", "full"), ("linux-firmware-none", "none")])
        self.boot_timeout = QLineEdit("3")
        self.extra_packages = QLineEdit("")
        self.extra_packages.setPlaceholderText("Space-separated apk packages, e.g. neovim tmux docker")
        self.package_search_worker = None
        self.package_search = QLineEdit("")
        self.package_search.setPlaceholderText("Search Alpine packages, e.g. firefox, docker, neovim")
        self.package_search_button = QPushButton("Search")
        self.package_search_button.setIcon(make_button_icon("refresh"))
        self.package_search_results = QListWidget()
        self.package_search_results.setMaximumHeight(150)
        self.package_search_results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.package_add_button = QPushButton("Add selected package(s)")
        self.package_add_button.setIcon(make_button_icon("check"))
        self.package_search_status = QLabel("Top 10 suggestions from Alpine main/community.")
        self.package_search_status.setStyleSheet("color:#cbd5e1;font-size:12px;")
        self.package_search.returnPressed.connect(self.search_packages)
        self.package_search_button.clicked.connect(self.search_packages)
        self.package_add_button.clicked.connect(self.add_selected_packages)
        self.package_search_results.itemDoubleClicked.connect(lambda _item: self.add_selected_packages())
        self.connect_config_change_signals()

    def connect_config_change_signals(self):
        def changed(*_args):
            self.refresh_build_summary()
        for widget in [
            self.image_size, self.alpine_branch, self.arch, self.timezone, self.locale,
            self.console_keymap, self.xkb_layout, self.desktop, self.display_manager,
            self.default_session, self.browser, self.audio, self.network, self.bootloader,
            self.kernel, self.firmware,
        ]:
            widget.currentTextChanged.connect(changed)
        for widget in [
            self.image, self.hostname, self.username, self.xkb_variant, self.xkb_model,
            self.boot_timeout, self.extra_packages,
        ]:
            widget.textChanged.connect(changed)
        for widget in [self.auto_resize, self.wifi, self.bluetooth, *self.wm_checks.values()]:
            widget.stateChanged.connect(changed)

    def checkbox_row(self, checkbox: QCheckBox, text: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background:transparent;border:0;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(text)
        label.setStyleSheet("background:transparent;border:0;color:#ffffff;")
        label.mousePressEvent = lambda _event: checkbox.toggle()
        row.mousePressEvent = lambda _event: checkbox.toggle()
        layout.addWidget(checkbox)
        layout.addWidget(label)
        layout.addStretch(1)
        return row

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
        header = QVBoxLayout(); header.setContentsMargins(0, 0, 0, 10); header.setSpacing(3)
        header.addWidget(title); header.addWidget(subtitle); layout.addLayout(header)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); content_layout = QVBoxLayout(content); content_layout.setContentsMargins(0, 0, 0, 0); content_layout.setSpacing(10)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        img_title = QLabel("1. Image configuration")
        img_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:6px 0px 2px 0px;padding:0px;")
        content_layout.addWidget(img_title)
        img_grid = QGridLayout(); img_grid.setColumnStretch(1, 1); img_grid.setHorizontalSpacing(10); img_grid.setVerticalSpacing(8)
        choose_output = QPushButton("Select path"); choose_output.setIcon(make_button_icon("folder")); choose_output.clicked.connect(self.choose_output_path); choose_output.setFixedWidth(120)
        self.build_button = QPushButton("Build image"); self.build_button.setIcon(make_button_icon("build")); self.build_button.clicked.connect(self.build_image); self.build_button.setFixedWidth(150)
        self.build_button.setStyleSheet("background:#16a34a;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:24px;")
        img_grid.addWidget(QLabel("Output path:"), 0, 0); img_grid.addWidget(self.image, 0, 1); img_grid.addWidget(choose_output, 0, 2)
        content_layout.addLayout(img_grid)

        config_note = QLabel("Configuration sections are collapsed by default; open only what you want to customize.")
        config_note.setStyleSheet("color:#cbd5e1;font-size:12px;margin-top:6px;")
        content_layout.addWidget(config_note)
        self.add_config_sections(content_layout)

        build_title = QLabel("2. Image build")
        build_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:10px 0px 2px 0px;padding:0px;")
        content_layout.addWidget(build_title)
        build_box = QVBoxLayout(); build_box.setSpacing(6)
        self.build_summary = QLabel("")
        self.build_summary.setWordWrap(True)
        self.build_summary.setTextFormat(Qt.TextFormat.RichText)
        self.build_summary.setStyleSheet("color:#cbd5e1;font-size:12px;margin:0px 0px 6px 0px;padding:8px;background:#0f172a;border:1px solid #374151;border-radius:6px;")
        build_box.addWidget(self.build_summary)
        self.refresh_build_summary()
        build_buttons = QHBoxLayout(); build_buttons.addWidget(self.build_button); build_buttons.addStretch(); build_box.addLayout(build_buttons)
        build_box.addWidget(self.build_status)
        self.build_progress = QProgressBar(); self.build_progress.setRange(0, 0); self.build_progress.hide(); build_box.addWidget(self.build_progress)
        content_layout.addLayout(build_box)

        usb_title = QLabel("3. USB target")
        usb_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:10px 0px 2px 0px;padding:0px;")
        content_layout.addWidget(usb_title)
        usb_box = QVBoxLayout(); usb_box.setSpacing(6)
        usb_row = QHBoxLayout(); usb_row.setSpacing(8)
        self.pick_button = QPushButton("Select USB"); self.pick_button.setIcon(make_button_icon("usb")); self.pick_button.clicked.connect(self.pick); self.pick_button.setFixedWidth(150)
        self.flash_button = QPushButton("Flash USB"); self.flash_button.setIcon(make_button_icon("flash")); self.flash_button.clicked.connect(self.flash); self.flash_button.setFixedWidth(150); self.flash_button.setEnabled(False)
        self.flash_button.setStyleSheet("""
            QPushButton { background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:24px; }
            QPushButton:disabled { background:#374151;color:#9ca3af; }
        """)
        device_label = QLabel("Device:"); device_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        usb_row.addWidget(device_label); usb_row.addWidget(self.device, 1); usb_row.addWidget(self.pick_button); usb_box.addLayout(usb_row)
        flash_row = QHBoxLayout(); flash_row.addWidget(self.flash_button); flash_row.addStretch(); usb_box.addLayout(flash_row)
        warn = QLabel("⚠ Flashing permanently erases the selected USB device.")
        warn.setStyleSheet("color:#fca5a5;font-weight:bold;margin:0px;padding:0px;font-size:12px;")
        usb_box.addWidget(warn); usb_box.addWidget(self.status)
        self.flash_progress = QProgressBar(); self.flash_progress.setRange(0, 100); self.flash_progress.setValue(0); self.flash_progress.hide(); usb_box.addWidget(self.flash_progress)
        content_layout.addLayout(usb_box)
        self.device.textChanged.connect(self.update_selected)
        content_layout.addStretch(1)

        console_box = QVBoxLayout(); console_box.setContentsMargins(0, 8, 0, 0); console_box.setSpacing(0)
        console_box.addWidget(self.console_toggle); console_box.addWidget(self.console_stack); layout.addLayout(console_box)

    def add_config_sections(self, parent_layout: QVBoxLayout):
        system = CollapsibleSection("System, user, localization", collapsed=True)
        form = QFormLayout(); form.setLabelAlignment(Qt.AlignmentFlag.AlignRight); form.setHorizontalSpacing(12); form.setVerticalSpacing(8)
        for label, widget in [
            ("Minimum image size:", self.image_size), ("Alpine branch:", self.alpine_branch), ("Architecture:", self.arch),
            ("Hostname:", self.hostname), ("User:", self.username), ("User password:", self.password),
            ("Root password:", self.root_password), ("", self.checkbox_row(self.show_passwords, self.show_passwords_label)), ("Timezone:", self.timezone), ("Locale:", self.locale),
            ("Console keymap:", self.console_keymap), ("XKB layout:", self.xkb_layout), ("XKB variant:", self.xkb_variant),
            ("XKB model:", self.xkb_model),
        ]:
            form.addRow(label, widget)
        system.body_layout.addLayout(form); parent_layout.addWidget(system)

        desktop = CollapsibleSection("Desktop environments, display manager and window managers", collapsed=True)
        dform = QFormLayout(); dform.setLabelAlignment(Qt.AlignmentFlag.AlignRight); dform.setHorizontalSpacing(12); dform.setVerticalSpacing(8)
        dform.addRow("Desktop:", self.desktop); dform.addRow("Display manager:", self.display_manager); dform.addRow("Default session:", self.default_session)
        dform.addRow("Browser:", self.browser); dform.addRow("Audio:", self.audio)
        desktop.body_layout.addLayout(dform)
        wm_label = QLabel("Optional tiling/window managers:"); wm_label.setStyleSheet("color:#cbd5e1;font-weight:bold;border:0;background:transparent;")
        desktop.body_layout.addWidget(wm_label)
        wm_grid = QGridLayout(); wm_grid.setHorizontalSpacing(18); wm_grid.setVerticalSpacing(6)
        for i, (key, cb) in enumerate(self.wm_checks.items()):
            wm_grid.addWidget(self.checkbox_row(cb, self.wm_labels[key]), i // 2, i % 2)
        desktop.body_layout.addLayout(wm_grid); parent_layout.addWidget(desktop)

        network = CollapsibleSection("Network, Wi‑Fi and Bluetooth", collapsed=True)
        nform = QFormLayout(); nform.setLabelAlignment(Qt.AlignmentFlag.AlignRight); nform.setHorizontalSpacing(12); nform.setVerticalSpacing(8)
        nform.addRow("Network backend:", self.network); nform.addRow("Wi‑Fi:", self.checkbox_row(self.wifi, self.wifi_label)); nform.addRow("Bluetooth:", self.checkbox_row(self.bluetooth, self.bluetooth_label))
        network.body_layout.addLayout(nform); parent_layout.addWidget(network)

        boot = CollapsibleSection("Bootloader, kernel and firmware", collapsed=True)
        bform = QFormLayout(); bform.setLabelAlignment(Qt.AlignmentFlag.AlignRight); bform.setHorizontalSpacing(12); bform.setVerticalSpacing(8)
        bform.addRow("Bootloader:", self.bootloader); bform.addRow("Kernel:", self.kernel); bform.addRow("Firmware:", self.firmware); bform.addRow("Boot menu timeout:", self.boot_timeout); bform.addRow("USB space:", self.checkbox_row(self.auto_resize, self.auto_resize_label))
        boot.body_layout.addLayout(bform); parent_layout.addWidget(boot)

        extra = CollapsibleSection("Extra APK packages", collapsed=True)
        extra.body_layout.addWidget(QLabel("Optional package names are passed directly to apk add. You can type several packages separated by spaces."))
        extra.body_layout.addWidget(self.extra_packages)
        extra.body_layout.addWidget(QLabel("Search official Alpine packages (enabled repos: main + community):"))
        search_row = QHBoxLayout(); search_row.setSpacing(8)
        search_row.addWidget(self.package_search, 1); search_row.addWidget(self.package_search_button)
        extra.body_layout.addLayout(search_row)
        extra.body_layout.addWidget(self.package_search_results)
        add_row = QHBoxLayout(); add_row.setSpacing(8)
        add_row.addWidget(self.package_add_button); add_row.addWidget(self.package_search_status, 1)
        extra.body_layout.addLayout(add_row)
        parent_layout.addWidget(extra)

    def search_packages(self):
        query = self.package_search.text().strip()
        if len(query) < 2:
            self.package_search_status.setText("Type at least 2 characters to search.")
            self.package_search_results.clear()
            return
        if self.thread_running(self.package_search_worker):
            self.package_search_status.setText("Search already running…")
            return
        branch = self.alpine_branch.currentText().strip() or "latest-stable"
        arch = combo_value(self.arch) or "x86_64"
        self.package_search_results.clear()
        self.package_search_status.setText(f"Searching {branch}/{arch} main + community…")
        self.package_search_button.setEnabled(False)
        self.package_search_worker = ApkSearchWorker(branch, arch, query)
        self.package_search_worker.done.connect(self.package_search_done)
        self.package_search_worker.failed.connect(self.package_search_failed)
        self.package_search_worker.finished.connect(self.package_search_finished)
        self.package_search_worker.start()

    def package_search_done(self, query: str, results: list):
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
        self.package_search_status.setText(f"Top {len(results)} suggestions. Double-click or select and add.")

    def package_search_failed(self, query: str, message: str):
        self.package_search_results.clear()
        self.package_search_status.setText(f"Search failed for '{query}': {message}")

    def package_search_finished(self):
        self.package_search_button.setEnabled(True)
        if self.sender() is self.package_search_worker:
            self.package_search_worker = None
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
        existing = [pkg for pkg in re.split(r"\s+", self.extra_packages.text().strip()) if pkg]
        existing_set = set(existing)
        added = []
        for name in names:
            if name not in existing_set:
                existing.append(name)
                existing_set.add(name)
                added.append(name)
        self.extra_packages.setText(" ".join(existing))
        self.package_search_status.setText("Added: " + ", ".join(added) if added else "Selected package(s) already added.")

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
        self.status.clear(); self.status.hide()
        self.build_status.clear(); self.build_status.hide()
        self.build_progress.hide(); self.flash_progress.hide()

    def pick(self):
        dlg = DeviceDialog(self)
        if dlg.exec() and dlg.selected:
            self.device.setText(dlg.selected)

    def update_selected(self):
        val = self.device.text().strip() or "none"
        self.setWindowTitle(f"{APP_TITLE} — {val}" if val != "none" else APP_TITLE)
        if not self.has_running_worker():
            self.flash_button.setEnabled(bool(val != "none" and self.image.text().strip()))

    def thread_running(self, thread):
        return thread is not None and thread.isRunning()

    def has_running_worker(self):
        return self.thread_running(self.builder) or self.thread_running(self.worker) or self.thread_running(self.package_search_worker)

    def set_busy(self, busy: bool):
        widgets = [
            self.build_button, self.pick_button, self.device, self.image,
            self.image_size, self.alpine_branch, self.arch, self.hostname,
            self.username, self.password, self.root_password, self.timezone,
            self.locale, self.console_keymap, self.xkb_layout, self.xkb_variant,
            self.xkb_model, self.desktop, self.display_manager, self.default_session,
            self.browser, self.audio, self.network, self.wifi, self.bluetooth,
            self.bootloader, self.kernel, self.firmware, self.boot_timeout,
            self.auto_resize, self.extra_packages, self.package_search,
            self.package_search_button, self.package_search_results, self.package_add_button,
        ] + list(self.wm_checks.values())
        for widget in widgets:
            widget.setEnabled(not busy)
        self.flash_button.setEnabled(False if busy else bool(self.device.text().strip() and self.image.text().strip()))

    def selected_wms(self) -> list[str]:
        return [key for key, cb in self.wm_checks.items() if cb.isChecked()]

    def collect_build_env(self) -> dict[str, str]:
        password = self.password.text()
        root_password = self.root_password.text() or password
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
        if not re.match(r"^[a-z_][a-z0-9_-]*$", env["ALPINE_USB_USER"]):
            return "Username must start with lowercase letter/_ and contain only lowercase letters, numbers, _ or -."
        if not env["ALPINE_USB_PASSWORD"]:
            return "User password cannot be empty."
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]$|^[A-Za-z0-9]$", env["ALPINE_USB_HOSTNAME"]):
            return "Hostname may contain only letters, numbers and dash; it cannot start/end with dash."
        if not env["ALPINE_USB_BOOT_TIMEOUT"].isdigit():
            return "Boot menu timeout must be a number."
        if env["ALPINE_USB_DESKTOP"] == "none" and not env["ALPINE_USB_TILING_WMS"] and env["ALPINE_USB_DISPLAY_MANAGER"] not in {"auto", "none", "greetd"}:
            return "Select a desktop/WM or use display manager Auto/None/greetd."
        session = env["ALPINE_USB_DEFAULT_SESSION"]
        if session == "auto":
            session = env["ALPINE_USB_DESKTOP"] if env["ALPINE_USB_DESKTOP"] != "none" else (env["ALPINE_USB_TILING_WMS"].split() or ["shell"])[0]
        if session in {"sway", "hyprland", "labwc"} and env["ALPINE_USB_DISPLAY_MANAGER"] in {"lightdm", "lxdm"}:
            return "Wayland sessions (Sway/Hyprland/labwc) need Auto, greetd, SDDM, GDM or no display manager; LightDM/LXDM are X11-only here."
        return None

    def config_summary_text(self, env: dict[str, str]) -> str:
        return (
            f"Size: {env['IMAGE_SIZE']} | Alpine: {env['ALPINE_BRANCH']} | "
            f"Desktop: {env['ALPINE_USB_DESKTOP']} | WMs: {env['ALPINE_USB_TILING_WMS'] or 'none'} | "
            f"DM: {env['ALPINE_USB_DISPLAY_MANAGER']} | Kernel: linux-{env['ALPINE_USB_KERNEL_FLAVOR']} | "
            f"Bootloader: {env['ALPINE_USB_BOOTLOADER']} | Auto-resize USB: {env['ALPINE_USB_AUTO_RESIZE']} | Wi‑Fi: {env['ALPINE_USB_WIFI']} | Bluetooth: {env['ALPINE_USB_BLUETOOTH']} | "
            f"Keyboard: {env['ALPINE_USB_XKB_LAYOUT']}"
        )

    def refresh_build_summary(self):
        if not hasattr(self, "build_summary"):
            return
        env = self.collect_build_env()
        extra = env.get("ALPINE_USB_EXTRA_PACKAGES", "").strip() or "none"
        self.build_summary.setText(
            "<b>Current configuration</b><br>"
            f"<b>Image:</b> {env['IMAGE_SIZE']} · Alpine {env['ALPINE_BRANCH']} · {env['ARCH']}<br>"
            f"<b>Desktop:</b> {env['ALPINE_USB_DESKTOP']} · DM {env['ALPINE_USB_DISPLAY_MANAGER']} · Session {env['ALPINE_USB_DEFAULT_SESSION']} · WMs {env['ALPINE_USB_TILING_WMS'] or 'none'}<br>"
            f"<b>Boot:</b> {env['ALPINE_USB_BOOTLOADER']} · linux-{env['ALPINE_USB_KERNEL_FLAVOR']} · firmware {env['ALPINE_USB_FIRMWARE']} · auto-resize {env['ALPINE_USB_AUTO_RESIZE']}<br>"
            f"<b>Hardware:</b> Wi‑Fi {env['ALPINE_USB_WIFI']} · Bluetooth {env['ALPINE_USB_BLUETOOTH']} · Audio {env['ALPINE_USB_AUDIO']} · Network {env['ALPINE_USB_NETWORK']}<br>"
            f"<b>Locale:</b> {env['ALPINE_USB_LOCALE']} · TZ {env['ALPINE_USB_TIMEZONE']} · Keyboard {env['ALPINE_USB_XKB_LAYOUT']}<br>"
            f"<b>Extra packages:</b> {extra}"
        )

    def build_image(self):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "Another operation is still running. Wait for it to finish.")
            return
        output_path = self.image.text().strip() or str(DEFAULT_OUTPUT_PATH)
        Path(output_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.refresh_build_summary()
        env = self.collect_build_env()
        validation_error = self.validate_build_config(env)
        if validation_error:
            modal(self, "error", APP_TITLE, validation_error)
            return
        if platform.system() == "Darwin":
            docker = find_executable("docker")
            if not docker:
                modal(self, "error", APP_TITLE, "Docker not found. Install Docker Desktop and try again. If it is installed, open Docker Desktop once so /usr/local/bin/docker is created.")
                return
            if subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                modal(self, "error", APP_TITLE, "Docker is not running. Start Docker Desktop and try again.")
                return
        confirm = f"Build Alpine image?\n\nOutput:\n{output_path}\n\n{self.config_summary_text(env)}"
        if not modal(self, "question", APP_TITLE, confirm, question=True):
            return
        self.build_progress.show(); self.flash_progress.hide()
        self.build_status.show(); self.build_status.setText("Building image...")
        self.status.hide(); self.set_busy(True)
        self.builder = BuildWorker(env, output_path)
        self.builder.log.connect(self.append_log)
        self.builder.done.connect(self.build_done)
        self.builder.finished.connect(self.build_thread_finished)
        self.builder.start()

    def build_done(self, ok, msg):
        self.build_progress.hide()
        self.build_status.show(); self.build_status.setText(msg)
        self.status.hide(); self.append_log(msg)
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
            modal(self, "error", APP_TITLE, "Image not found."); return
        if not dev:
            modal(self, "error", APP_TITLE, "Select USB device."); return
        if not modal(self, "question", APP_TITLE, f"Erase and flash?\n\n{dev}\n\nImage: {img}", question=True):
            return
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
        self.build_progress.hide(); self.flash_progress.setRange(0, 100); self.flash_progress.setValue(0); self.flash_progress.show()
        self.status.show(); self.status.setText("Flashing... 0%")
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
        self.flash_progress.hide(); self.status.show(); self.status.setText(msg)
        self.append_log(msg); self.set_busy(False)
        modal(self, "info" if ok else "error", APP_TITLE, msg)

    def flash_thread_finished(self):
        if self.sender() is self.worker:
            self.worker = None

    def closeEvent(self, event):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "An operation is still running. Wait for it to finish before closing the app.")
            event.ignore(); return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(make_app_icon())
    w = Main(); w.show()
    QTimer.singleShot(0, lambda: ensure_widget_visible(w))
    sys.exit(app.exec())
