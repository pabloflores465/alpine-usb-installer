#!/usr/bin/env python3
from __future__ import annotations

import os, platform, plistlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QProgressBar, QVBoxLayout, QWidget,
    QDialog, QTextEdit
)

APP_TITLE = "Alpine USB XFCE Installer"


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
        self.manual = QLineEdit("/dev/disk7" if platform.system() == "Darwin" else "/dev/sdX")
        row.addWidget(self.manual, 1)
        layout.addLayout(row)
        btns = QHBoxLayout()
        self.use = QPushButton("Use selected")
        self.refresh = QPushButton("Refresh")
        self.cancel = QPushButton("Cancel")
        btns.addWidget(self.use); btns.addWidget(self.refresh); btns.addStretch(); btns.addWidget(self.cancel)
        layout.addLayout(btns)
        self.use.clicked.connect(self.accept_selection)
        self.refresh.clicked.connect(self.populate)
        self.cancel.clicked.connect(self.reject)
        self.populate()

    def populate(self):
        self.list.clear()
        self.devices = list_devices()
        for _, label in self.devices:
            self.list.addItem(label)
        if self.devices:
            self.list.setCurrentRow(0)

    def accept_selection(self):
        item = self.list.currentItem()
        if item:
            self.selected = item.text()
        else:
            self.selected = self.manual.text().strip()
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
                    "apk add --no-cache bash curl sudo e2fsprogs dosfstools util-linux sfdisk "
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

    def __init__(self, image: str, label: str):
        super().__init__()
        self.image = image
        self.label = label

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
                inner = (
                    f"/bin/dd if={sh_quote(tmp_image)} of={sh_quote(raw)} bs=4m 2>>{sh_quote(log_path)} & "
                    "pid=$!; while kill -0 $pid 2>/dev/null; do kill -INFO $pid 2>/dev/null || true; sleep 2; done; wait $pid; "
                    f"echo __DONE__$? >> {sh_quote(log_path)}"
                )
                cmd = (
                    f"diskutil unmountDisk {sh_quote(dev)} >> {sh_quote(log_path)} 2>&1 && "
                    f"/bin/sh -c {sh_quote(inner)} && sync && "
                    f"diskutil eject {sh_quote(dev)} >> {sh_quote(log_path)} 2>&1"
                )
                proc = subprocess.Popen(["osascript", "-e", f'do shell script {cmd!r} with administrator privileges'])
                pos = 0
                last_percent = -1
                while proc.poll() is None:
                    pos, last_percent = self.tail_progress(log_path, pos, total, last_percent)
                    self.msleep(500)
                pos, last_percent = self.tail_progress(log_path, pos, total, last_percent)
                if proc.returncode:
                    raise RuntimeError(f"Flashing failed with exit code {proc.returncode}")
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
        self.resize(900, 560)
        self.image = QLineEdit(str(Path.cwd() / "alpine-usb-xfce.img"))
        self.image.setReadOnly(False)
        self.image.setPlaceholderText("Output image path, e.g. /Users/you/Downloads/alpine-usb-xfce.img")
        self.image_size = QLineEdit("16G")
        self.device = QLineEdit()
        self.status = QLabel("")
        self.status.setStyleSheet("color:#d1d5db;")
        self.status.hide()
        self.console_title = QLabel("Console output")
        self.console_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin-top:6px;")
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setMinimumHeight(240)
        self.log.setMaximumHeight(360)
        self.build()
        self.refresh()

    def build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)
        title = QLabel("Alpine USB XFCE Installer")
        self.setStyleSheet("""
            QWidget { background:#111827; color:#ffffff; }
            QLabel { color:#ffffff; }
            QLineEdit { background:#1f2937; color:#ffffff; border:1px solid #4b5563; border-radius:4px; padding:4px; }
            QTextEdit { background:#0b1220; color:#ffffff; border:1px solid #374151; border-radius:6px; }
            QPushButton { background:#2563eb; color:#ffffff; border:0; border-radius:6px; padding:6px 10px; }
            QPushButton:hover { background:#1d4ed8; }
            QPushButton:disabled { background:#4b5563; color:#d1d5db; }
            QListWidget { background:#0b1220; color:#ffffff; border:1px solid #374151; }
            QProgressBar { color:#ffffff; }
        """)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#ffffff;")
        subtitle = QLabel("Build and flash a preconfigured Alpine Linux XFCE USB image.")
        subtitle.setStyleSheet("color:#cbd5e1;margin-bottom:4px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        img_title = QLabel("1. Image")
        img_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin-top:6px;")
        layout.addWidget(img_title)
        img_grid = QGridLayout()
        img_grid.setContentsMargins(0, 0, 0, 0)
        img_grid.setColumnStretch(1, 1)
        img_grid.setHorizontalSpacing(8)
        img_grid.setVerticalSpacing(3)
        choose_output = QPushButton("Select path")
        choose_output.clicked.connect(self.choose_output_path)
        choose_output.setFixedWidth(120)
        build = QPushButton("Build image")
        build.clicked.connect(self.build_image)
        build.setFixedWidth(150)
        build.setStyleSheet("background:#16a34a;color:#ffffff;border:0;border-radius:6px;padding:6px 10px;font-weight:bold;")
        self.image_size.hide()
        img_grid.addWidget(QLabel("Output path:"), 0, 0)
        img_grid.addWidget(self.image, 0, 1)
        img_grid.addWidget(choose_output, 0, 2)
        img_grid.addWidget(build, 0, 3)
        layout.addLayout(img_grid)

        usb_title = QLabel("2. USB target")
        usb_title.setStyleSheet("font-size:15px;font-weight:bold;color:#93c5fd;margin-top:6px;")
        layout.addWidget(usb_title)
        usb_box = QVBoxLayout()
        usb_box.setContentsMargins(0, 0, 0, 0)
        usb_box.setSpacing(1)
        usb_row = QHBoxLayout()
        usb_row.setContentsMargins(0, 0, 0, 0)
        usb_row.setSpacing(4)
        pick = QPushButton("Select USB")
        pick.clicked.connect(self.pick)
        pick.setFixedWidth(150)
        flash = QPushButton("Flash USB")
        flash.clicked.connect(self.flash)
        flash.setFixedWidth(150)
        flash.setStyleSheet("background:#dc2626;color:#ffffff;border:0;border-radius:6px;padding:7px 12px;font-weight:bold;")
        device_label = QLabel("Device:")
        device_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        usb_row.addWidget(device_label)
        usb_row.addWidget(self.device, 1)
        usb_row.addWidget(pick)
        usb_row.addWidget(flash)
        usb_box.addLayout(usb_row)
        warn = QLabel("⚠ Flashing permanently erases the selected USB device.")
        warn.setStyleSheet("color:#fca5a5;font-weight:bold;margin:0px;padding:0px;")
        warn.setContentsMargins(58, 0, 0, 0)
        usb_box.addWidget(warn)
        layout.addLayout(usb_box)
        self.device.textChanged.connect(self.update_selected)
        self.progress = QProgressBar(); self.progress.setRange(0,0); self.progress.hide(); layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.console_title)
        layout.addWidget(self.log)

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
        devs = list_devices()
        if devs and not self.device.text().strip():
            self.device.setText(devs[0][1])
        self.status.clear()
        self.status.hide()

    def pick(self):
        dlg = DeviceDialog(self)
        if dlg.exec() and dlg.selected:
            self.device.setText(dlg.selected)

    def update_selected(self):
        val = self.device.text().strip() or "none"
        self.setWindowTitle(f"{APP_TITLE} — {val}" if val != "none" else APP_TITLE)

    def build_image(self):
        size = self.image_size.text().strip() or "16G"
        output_path = self.image.text().strip() or str(Path.cwd() / "alpine-usb-xfce.img")
        if platform.system() == "Darwin" and not shutil.which("docker"):
            QMessageBox.critical(self, APP_TITLE, "Docker not found. Install/start Docker Desktop.")
            return
        if not QMessageBox.question(self, APP_TITLE, f"Build Alpine image?\n\nOutput:\n{output_path}") == QMessageBox.Yes:
            return
        self.progress.show()
        self.status.show()
        self.status.setText("Building image...")
        self.builder = BuildWorker(size, output_path)
        self.builder.log.connect(self.append_log)
        self.builder.done.connect(self.build_done)
        self.builder.start()

    def build_done(self, ok, msg):
        self.progress.hide()
        self.status.show()
        self.status.setText(msg)
        self.log.append(msg)
        if ok:
            m = re.search(r"Image build complete: (.+)$", msg)
            if m:
                self.image.setText(m.group(1))
        (QMessageBox.information if ok else QMessageBox.critical)(self, APP_TITLE, msg)

    def flash(self):
        img = self.image.text().strip()
        dev = self.device.text().strip()
        if not Path(img).exists():
            QMessageBox.critical(self, APP_TITLE, "Image not found."); return
        if not dev:
            QMessageBox.critical(self, APP_TITLE, "Select USB device."); return
        if not QMessageBox.question(self, APP_TITLE, f"Erase and flash?\n\n{dev}\n\nImage: {img}") == QMessageBox.Yes:
            return
        self.progress.show()
        self.status.show()
        self.worker = FlashWorker(img, dev)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.status.setText)
        self.worker.done.connect(self.flash_done)
        self.worker.start()

    def append_log(self, line):
        self.log.append(line)
        if self.log.document().blockCount() > 300:
            cursor = self.log.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def flash_done(self, ok, msg):
        self.progress.hide()
        self.status.show()
        self.status.setText(msg)
        self.log.append(msg)
        (QMessageBox.information if ok else QMessageBox.critical)(self, APP_TITLE, msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Main(); w.show()
    sys.exit(app.exec())
