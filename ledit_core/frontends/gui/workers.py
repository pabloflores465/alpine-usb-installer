from __future__ import annotations

import contextlib
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable

from PySide6.QtCore import QThread, QTimer, Signal

from ledit_core.image_builds.execution import ImageBuildRunner
from ledit_core.images.validation import validate_usb_image
from ledit_core.package_search import DistroPackageSearchService, PackageSearchRequest
from ledit_core.usb_devices.detection import device_safety_report, list_devices


class DeviceScanWorker(QThread):
    done = Signal(list)

    def run(self):
        self.done.emit(list_devices())


class PackageSearchWorker(QThread):
    done = Signal(str, list)
    failed = Signal(str, str)

    def __init__(
        self,
        distro: str,
        branch: str,
        arch: str,
        query: str,
        search_service_factory: Callable[[], DistroPackageSearchService] = DistroPackageSearchService,
    ):
        super().__init__()
        self.distro = distro
        self.branch = branch
        self.arch = arch
        self.query = query
        self.search_service_factory = search_service_factory

    def run(self):
        try:
            results = self.search_service_factory().search(
                PackageSearchRequest(distro=self.distro, branch=self.branch, arch=self.arch, query=self.query, limit=10)
            )
            self.done.emit(self.query, results)
        except Exception as exc:
            self.failed.emit(self.query, str(exc))


class BuildWorker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, config_env: dict[str, str], output_path: str, runner: ImageBuildRunner):
        super().__init__()
        self.config_env = config_env
        self.output_path = output_path
        self.runner = runner

    def force_cancel(self):
        self.runner.force_cancel(self.log.emit)

    def cancel(self):
        self.runner.cancel(self.log.emit)
        QTimer.singleShot(5000, self.force_cancel)

    def run(self):
        result = self.runner.run({k: str(v) for k, v in self.config_env.items()}, self.output_path, self.log.emit)
        self.done.emit(result.ok, result.message)


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


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
            image_check = validate_usb_image(self.image)
            if not image_check.ok:
                raise RuntimeError(image_check.reason or "Image failed validation")
            ok_safe, dev, _rows, reason = device_safety_report(dev)
            if not ok_safe:
                raise RuntimeError(reason or "Unsafe USB target")
            if platform.system() == "Darwin":
                raw = dev.replace("/dev/disk", "/dev/rdisk")
                image_for_dd = self.image
                log_path = os.path.join(tempfile.gettempdir(), "ledit-flash.log")
                with contextlib.suppress(FileNotFoundError):
                    os.remove(log_path)
                total = os.path.getsize(image_for_dd)
                if not self.sudo_password:
                    raise RuntimeError("Administrator password is required to flash the USB.")
                with open(log_path, "w") as log:
                    log.write("LEDIT - Flash USB\n")
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


# Backward-compatible local name used by gui.py until UI wording is fully renamed.
ApkSearchWorker = PackageSearchWorker
