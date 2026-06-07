#!/usr/bin/env python3
from __future__ import annotations

import os, platform, plistlib, re, shutil, subprocess, sys, tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
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
                    name = meta.get("MediaName") or meta.get("IORegistryEntryName") or "USB"
                    label = f"{dev} ({size}) {name}"
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


class FlashWorker(QThread):
    log = Signal(str)
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
                script = os.path.join(tempfile.gettempdir(), "alpine-usb-flash.sh")
                inner = (
                    f"/bin/dd if={sh_quote(tmp_image)} of={sh_quote(raw)} bs=4m & "
                    "pid=$!; while kill -0 $pid 2>/dev/null; do kill -INFO $pid 2>/dev/null || true; sleep 2; done; wait $pid"
                )
                with open(script, "w") as fh:
                    fh.write("#!/bin/sh\nset -e\n")
                    fh.write(f"diskutil unmountDisk {sh_quote(dev)}\n")
                    fh.write(f"echo 'Flashing {tmp_image} -> {raw}'\n")
                    fh.write(f"sudo /bin/sh -c {sh_quote(inner)}\n")
                    fh.write("sync\n")
                    fh.write(f"diskutil eject {sh_quote(dev)}\n")
                    fh.write("echo 'DONE. USB ejected.'\n")
                os.chmod(script, 0o755)
                subprocess.Popen(["/bin/sh", script])
                self.done.emit(True, "Flashing started in launching terminal backend.")
            elif platform.system() == "Linux":
                cmd = ["dd", f"if={self.image}", f"of={dev}", "bs=4M", "status=progress", "conv=fsync"]
                if os.geteuid() != 0:
                    cmd.insert(0, shutil.which("pkexec") or "sudo")
                subprocess.Popen(cmd)
                self.done.emit(True, "Flashing started in backend.")
            else:
                raise RuntimeError("Windows flashing not implemented. Use Rufus/balenaEtcher.")
        except Exception as e:
            self.done.emit(False, str(e))


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(760, 460)
        self.image = QLineEdit(str(Path.cwd() / "alpine-usb-xfce.img"))
        self.device = QLineEdit()
        self.selected = QLabel("Selected USB: none")
        self.selected.setStyleSheet("background:#ecfdf5;color:#065f46;font-weight:bold;padding:10px;border:1px solid #10b981;")
        self.status = QLabel("Select image and USB device.")
        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setMaximumHeight(130)
        self.build()
        self.refresh()

    def build(self):
        layout = QVBoxLayout(self)
        title = QLabel("Alpine USB XFCE Installer")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Flash a preconfigured Alpine Linux XFCE image to a USB drive."))
        row = QHBoxLayout(); row.addWidget(QLabel("Image:")); row.addWidget(self.image, 1)
        browse = QPushButton("Browse image"); browse.clicked.connect(self.browse); row.addWidget(browse); layout.addLayout(row)
        row = QHBoxLayout(); row.addWidget(QLabel("USB device:")); row.addWidget(self.device, 1)
        pick = QPushButton("Select USB"); pick.clicked.connect(self.pick); row.addWidget(pick)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh); row.addWidget(refresh); layout.addLayout(row)
        self.device.textChanged.connect(self.update_selected)
        layout.addWidget(self.selected)
        warn = QLabel("WARNING: Flashing will permanently erase selected USB device.")
        warn.setStyleSheet("color:#b91c1c;font-weight:bold;")
        layout.addWidget(warn)
        flash = QPushButton("Flash USB"); flash.clicked.connect(self.flash); layout.addWidget(flash)
        self.progress = QProgressBar(); self.progress.setRange(0,0); self.progress.hide(); layout.addWidget(self.progress)
        layout.addWidget(self.status); layout.addWidget(self.log)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select image", "", "Images (*.img *.raw *.iso);;All files (*)")
        if path: self.image.setText(path)

    def refresh(self):
        devs = list_devices()
        if devs and not self.device.text().strip():
            self.device.setText(devs[0][1])
        self.status.setText(f"Found {len(devs)} removable device(s)." if devs else "No USB found. Use Select USB/manual device.")

    def pick(self):
        dlg = DeviceDialog(self)
        if dlg.exec() and dlg.selected:
            self.device.setText(dlg.selected)
            QMessageBox.information(self, "USB selected", f"Selected USB:\n{dlg.selected}")

    def update_selected(self):
        val = self.device.text().strip() or "none"
        self.selected.setText(f"Selected USB: {val}")
        self.setWindowTitle(f"{APP_TITLE} — {val}" if val != "none" else APP_TITLE)

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
        self.worker = FlashWorker(img, dev)
        self.worker.done.connect(self.flash_done)
        self.worker.start()

    def flash_done(self, ok, msg):
        self.progress.hide()
        self.status.setText(msg)
        self.log.append(msg)
        (QMessageBox.information if ok else QMessageBox.critical)(self, APP_TITLE, msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Main(); w.show()
    sys.exit(app.exec())
