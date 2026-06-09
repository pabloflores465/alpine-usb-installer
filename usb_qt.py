#!/usr/bin/env python3
from __future__ import annotations

import os, platform, plistlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QProgressBar, QVBoxLayout, QWidget,
    QDialog, QInputDialog, QStyle, QTextEdit
)

APP_TITLE = "Alpine USB XFCE Installer"


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
    def xy(v): return int(v * scale)
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
    elif kind == "check":
        p.drawLine(xy(4), xy(10), xy(8), xy(15)); p.drawLine(xy(8), xy(15), xy(16), xy(5))
    elif kind == "warn":
        p.drawPolyline(pts([(xy(10), xy(3)), (xy(18), xy(17)), (xy(2), xy(17)), (xy(10), xy(3))])); p.drawLine(xy(10), xy(7), xy(10), xy(12)); p.drawPoint(xy(10), xy(15))
    elif kind == "error":
        p.drawEllipse(xy(3), xy(3), xy(14), xy(14)); p.drawLine(xy(7), xy(7), xy(13), xy(13)); p.drawLine(xy(13), xy(7), xy(7), xy(13))
    p.end()
    return QIcon(pix)


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
        box.exec()
        return box.clickedButton() == ok
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    ok = box.button(QMessageBox.StandardButton.Ok)
    if ok:
        ok.setIcon(make_button_icon("check"))
        ok.setStyleSheet("background:#2563eb;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
    box.exec()
    return True


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def list_devices():
    sysname = platform.system()
    devices = []
    if sysname == "Darwin":
        cp = run(["diskutil", "list", "-plist", "external", "physical"])
        try:
            data = plistlib.loads(cp.stdout.encode())
            for disk in data.get("AllDisksAndPartitions", []):
                ident = disk.get("DeviceIdentifier")
                if not ident: continue
                dev = f"/dev/{ident}"
                info = run(["diskutil", "info", "-plist", dev])
                label = dev
                try:
                    meta = plistlib.loads(info.stdout.encode())
                    size_bytes = int(meta.get("TotalSize", 0) or 0)
                    size = f"{size_bytes / 1_000_000_000:.1f} GB" if size_bytes else "unknown size"
                    # Prefer IORegistryEntryName because it often includes the brand
                    # shown on the physical USB, e.g. "Kingston DataTraveler 3.0 Media".
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


class DeviceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select USB device")
        self.resize(620, 380)
        self.selected = None
        layout = QVBoxLayout(self)
        title = QLabel("Select target USB device")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        warn = QLabel("WARNING: selected device will be erased.")
        warn.setStyleSheet("color: #b91c1c; font-weight: bold;")
        layout.addWidget(warn)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
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
        self.refresh.setIcon(make_button_icon("build"))
        self.cancel = QPushButton("Cancel")
        self.cancel.setIcon(make_button_icon("error"))
        self.cancel.setStyleSheet("background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:6px 12px;font-weight:bold;")
        btns.addWidget(self.use); btns.addWidget(self.refresh); btns.addStretch(); btns.addWidget(self.cancel)
        layout.addLayout(btns)
        self.use.clicked.connect(self.accept_selection)
        self.refresh.clicked.connect(lambda: self.populate(show_empty_modal=True))
        self.cancel.clicked.connect(self.reject)
        self.list.itemSelectionChanged.connect(self.update_use_button)
        self.manual.textChanged.connect(self.update_use_button)
        self.populate(show_empty_modal=True)

    def populate(self, show_empty_modal: bool = True):
        self.list.clear()
        self.devices = list_devices()
        for _, label in self.devices:
            self.list.addItem(label)
        self.list.clearSelection()
        self.update_use_button()
        if show_empty_modal and not self.devices:
            modal(self, "info", APP_TITLE, "No USB devices were found. Connect a USB drive and click Refresh to scan again.")

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


class BuildWorker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, image_size: str, output_path: str):
        super().__init__()
        self.image_size = image_size
        self.output_path = output_path

    def run(self):
        try:
            env = os.environ.copy()
            env["IMAGE_SIZE"] = self.image_size
            cmd = ["./build-alpine-usb.sh"]
            if platform.system() == "Darwin":
                # Build script works inside Docker Desktop on macOS.
                docker_cmd = (
                    "apk add --no-cache bash curl sudo python3 e2fsprogs dosfstools util-linux sfdisk "
                    "multipath-tools qemu-img qemu-system-x86_64 parted grub grub-efi mtools "
                    "xorriso rsync kmod >/dev/null && "
                    "rm -f alpine-usb-xfce.img && "
                    "chmod +x .work/alpine-make-vm-image.uefi build-alpine-usb.sh configure-alpine-usb.sh && "
                    f"IMAGE_SIZE={self.image_size} ./build-alpine-usb.sh"
                )
                cmd = [
                    "docker", "run", "--rm", "--platform", "linux/amd64", "--privileged",
                    "-v", f"{os.getcwd()}:/work", "-w", "/work", "alpine:latest", "sh", "-c", docker_cmd
                ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            for line in proc.stdout or []:
                self.log.emit(line.rstrip())
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"Build failed with exit code {code}")
            built = str(Path.cwd() / "alpine-usb-xfce.img")
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
                tmp_image = os.path.join(tempfile.gettempdir(), "alpine-usb-xfce.img")
                try: os.remove(tmp_image)
                except FileNotFoundError: pass
                try:
                    os.link(self.image, tmp_image)
                except OSError:
                    # fallback only if link impossible
                    shutil.copyfile(self.image, tmp_image)
                log_path = os.path.join(tempfile.gettempdir(), "alpine-usb-flash.log")
                try: os.remove(log_path)
                except FileNotFoundError: pass
                total = os.path.getsize(tmp_image)
                if not self.sudo_password:
                    raise RuntimeError("Administrator password is required to flash the USB.")
                with open(log_path, "w") as log:
                    log.write("Alpine USB XFCE Installer - Flash USB\n")
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
        self.resize(900, 480)
        self.image = QLineEdit(str(Path.cwd() / "alpine-usb-xfce.img"))
        self.image.setReadOnly(False)
        self.image.setPlaceholderText("Output image path, e.g. /Users/you/Downloads/alpine-usb-xfce.img")
        self.image_size = QLineEdit("16G")
        self.device = QLineEdit()
        self.status = QLabel("")
        self.status.setStyleSheet("color:#d1d5db;")
        self.status.hide()
        self.build_status = QLabel("")
        self.build_status.setStyleSheet("color:#d1d5db;margin-top:8px;padding:0px;font-size:12px;")
        self.build_status.hide()
        self.builder = None
        self.worker = None
        self.console_toggle = QPushButton("Console output  ▼")
        self.console_toggle.clicked.connect(self.toggle_console)
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setMinimumHeight(320)
        self.log.setMaximumHeight(520)
        self.update_console_style(expanded=True)
        self.build()
        self.refresh()

    def build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        title = QLabel("Alpine USB XFCE Installer")
        self.setStyleSheet("""
            QWidget { background:#111827; color:#ffffff; }
            QLabel { color:#ffffff; margin:0px; padding:0px; }
            QLineEdit { background:#1f2937; color:#ffffff; border:1px solid #4b5563; border-radius:4px; padding:1px 4px; min-height:22px; max-height:24px; }
            QTextEdit { background:#0b1220; color:#ffffff; border:1px solid #374151; border-radius:6px; }
            QPushButton { background:#2563eb; color:#ffffff; border:0; border-radius:6px; padding:3px 8px; min-height:22px; max-height:26px; }
            QPushButton:hover { background:#1d4ed8; }
            QPushButton:disabled { background:#4b5563; color:#d1d5db; }
            QListWidget { background:#0b1220; color:#ffffff; border:1px solid #374151; }
            QProgressBar { color:#ffffff; }
        """)
        title.setStyleSheet("font-size:20px;font-weight:bold;color:#ffffff;margin:0px;padding:0px;")
        subtitle = QLabel("Build and flash a preconfigured Alpine Linux XFCE USB image.")
        subtitle.setStyleSheet("color:#cbd5e1;margin:0px;padding:0px;font-size:12px;")
        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 10)
        header.setSpacing(3)
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)
        img_title = QLabel("1. Image")
        img_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:6px 0px 2px 0px;padding:0px;")
        layout.addWidget(img_title)
        img_grid = QGridLayout()
        img_grid.setContentsMargins(0, 0, 0, 0)
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
        self.build_button.setStyleSheet("background:#16a34a;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:22px;max-height:26px;")
        self.image_size.hide()
        img_grid.addWidget(QLabel("Output path:"), 0, 0)
        img_grid.addWidget(self.image, 0, 1)
        img_grid.addWidget(choose_output, 0, 2)
        img_buttons = QHBoxLayout()
        img_buttons.setContentsMargins(0, 10, 0, 0)
        img_buttons.addWidget(self.build_button)
        img_buttons.addStretch()
        img_grid.addLayout(img_buttons, 1, 0, 1, 3)
        img_grid.addWidget(self.build_status, 2, 0, 1, 3)
        self.build_progress = QProgressBar(); self.build_progress.setRange(0,0); self.build_progress.hide()
        img_grid.addWidget(self.build_progress, 3, 0, 1, 3)
        layout.addLayout(img_grid)
        layout.addSpacing(12)

        usb_title = QLabel("2. USB target")
        usb_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin:6px 0px 2px 0px;padding:0px;")
        layout.addWidget(usb_title)
        usb_box = QVBoxLayout()
        usb_box.setContentsMargins(0, 0, 0, 0)
        usb_box.setSpacing(6)
        usb_row = QHBoxLayout()
        usb_row.setContentsMargins(0, 0, 0, 0)
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
            QPushButton { background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:3px 8px;font-weight:bold;min-height:22px;max-height:26px; }
            QPushButton:disabled { background:#374151;color:#9ca3af; }
        """)
        device_label = QLabel("Device:")
        device_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        usb_row.addWidget(device_label)
        usb_row.addWidget(self.device, 1)
        usb_row.addWidget(self.pick_button)
        usb_box.addLayout(usb_row)
        flash_row = QHBoxLayout()
        flash_row.setContentsMargins(0, 10, 0, 0)
        flash_row.addWidget(self.flash_button)
        flash_row.addStretch()
        usb_box.addLayout(flash_row)
        warn = QLabel("⚠ Flashing permanently erases the selected USB device.")
        warn.setStyleSheet("color:#fca5a5;font-weight:bold;margin:0px;padding:0px;font-size:12px;")
        warn.setContentsMargins(0, 12, 0, 0)
        usb_box.addWidget(warn)
        usb_box.addSpacing(10)
        usb_box.addWidget(self.status)
        self.flash_progress = QProgressBar(); self.flash_progress.setRange(0,100); self.flash_progress.setValue(0); self.flash_progress.hide()
        usb_box.addWidget(self.flash_progress)
        layout.addLayout(usb_box)
        self.device.textChanged.connect(self.update_selected)
        layout.addSpacing(14)
        console_box = QVBoxLayout()
        console_box.setContentsMargins(0, 0, 0, 0)
        console_box.setSpacing(0)
        console_box.addWidget(self.console_toggle)
        console_box.addWidget(self.log)
        layout.addLayout(console_box)
        layout.addStretch(1)

    def update_console_style(self, expanded: bool):
        if expanded:
            self.console_toggle.setStyleSheet(
                "text-align:left;font-size:15px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:5px 10px;background:#1f2937;"
                "border:1px solid #374151;border-bottom:0;"
                "border-top-left-radius:6px;border-top-right-radius:6px;"
                "border-bottom-left-radius:0px;border-bottom-right-radius:0px;"
            )
            self.log.setStyleSheet(
                "background:#0b1220;color:#ffffff;border:1px solid #374151;"
                "border-top:0;border-top-left-radius:0px;border-top-right-radius:0px;"
                "border-bottom-left-radius:6px;border-bottom-right-radius:6px;"
            )
        else:
            self.console_toggle.setStyleSheet(
                "text-align:left;font-size:15px;font-weight:bold;color:#93c5fd;"
                "margin:0px;padding:5px 10px;background:#1f2937;"
                "border:1px solid #374151;border-radius:6px;"
            )

    def toggle_console(self):
        visible = self.log.isVisible()
        expanded = not visible
        self.log.setVisible(expanded)
        self.console_toggle.setText("Console output  ▼" if expanded else "Console output  ▲")
        self.update_console_style(expanded)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select image", "", "Images (*.img *.raw *.iso);;All files (*)")
        if path: self.image.setText(path)

    def choose_output_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select output image path",
            self.image.text().strip() or str(Path.cwd() / "alpine-usb-xfce.img"),
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
        if not self.has_running_worker():
            self.flash_button.setEnabled(bool(val != "none" and self.image.text().strip()))

    def thread_running(self, thread):
        return thread is not None and thread.isRunning()

    def has_running_worker(self):
        return self.thread_running(self.builder) or self.thread_running(self.worker)

    def set_busy(self, busy: bool):
        self.build_button.setEnabled(not busy)
        self.pick_button.setEnabled(not busy)
        self.device.setEnabled(not busy)
        self.image.setEnabled(not busy)
        self.flash_button.setEnabled(False if busy else bool(self.device.text().strip() and self.image.text().strip()))

    def build_image(self):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "Another operation is still running. Wait for it to finish.")
            return
        size = self.image_size.text().strip() or "16G"
        output_path = self.image.text().strip() or str(Path.cwd() / "alpine-usb-xfce.img")
        if platform.system() == "Darwin" and not shutil.which("docker"):
            modal(self, "error", APP_TITLE, "Docker not found. Install/start Docker Desktop.")
            return
        if not modal(self, "question", APP_TITLE, f"Build Alpine image?\n\nOutput:\n{output_path}", question=True):
            return
        self.build_progress.show()
        self.flash_progress.hide()
        self.build_status.show()
        self.build_status.setText("Building image...")
        self.status.hide()
        self.set_busy(True)
        self.builder = BuildWorker(size, output_path)
        self.builder.log.connect(self.append_log)
        self.builder.done.connect(self.build_done)
        self.builder.finished.connect(self.build_thread_finished)
        self.builder.start()

    def build_done(self, ok, msg):
        self.build_progress.hide()
        self.build_status.show()
        self.build_status.setText(msg)
        self.status.hide()
        self.log.append(msg)
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
        self.build_progress.hide()
        self.flash_progress.setRange(0,100)
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
        self.log.append(msg)
        self.set_busy(False)
        modal(self, "info" if ok else "error", APP_TITLE, msg)

    def flash_thread_finished(self):
        if self.sender() is self.worker:
            self.worker = None

    def closeEvent(self, event):
        if self.has_running_worker():
            modal(self, "error", APP_TITLE, "An operation is still running. Wait for it to finish before closing the app.")
            event.ignore()
            return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(make_app_icon())
    w = Main(); w.show()
    sys.exit(app.exec())
