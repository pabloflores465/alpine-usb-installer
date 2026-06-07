#!/usr/bin/env python3
"""Simple cross-platform GUI to flash Alpine USB images.

Supports macOS and Linux. Windows support is intentionally conservative: it can
select an image, but raw flashing is not implemented to avoid unsafe drive use.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Alpine USB XFCE Installer"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)


def list_devices() -> list[tuple[str, str]]:
    sys = platform.system()
    devices: list[tuple[str, str]] = []
    if sys == "Darwin":
        cp = run(["diskutil", "list", "external", "physical"])
        current = None
        for line in cp.stdout.splitlines():
            m = re.match(r"(/dev/disk\d+) \(external, physical\):", line)
            if m:
                current = m.group(1)
                continue
            if current and "GUID_partition_scheme" in line or (current and "FDisk_partition_scheme" in line) or (current and "*" in line and "disk" not in line):
                pass
        # Better parse all external disks with size from first block line.
        blocks = cp.stdout.split("/dev/")
        for block in blocks:
            if not block.startswith("disk"):
                continue
            first = "/dev/" + block.splitlines()[0].split()[0]
            size = "unknown size"
            for line in block.splitlines():
                if "*" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        size = " ".join(parts[-3:-1]) if parts[-1].startswith("disk") else " ".join(parts[-2:])
                    break
            devices.append((first, f"{first} ({size})"))
    elif sys == "Linux":
        cp = run(["lsblk", "-dpno", "NAME,SIZE,TRAN,TYPE,MODEL"])
        for line in cp.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4 and parts[3] == "disk":
                name, size, tran = parts[0], parts[1], parts[2]
                model = parts[4] if len(parts) > 4 else ""
                if tran in {"usb", "mmc"} or name.startswith("/dev/sd"):
                    devices.append((name, f"{name} ({size}) {model}".strip()))
    return devices


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("820x520")
        self.resizable(True, True)
        self.configure(bg="#f3f4f6")

        self.image_var = tk.StringVar(value=str(Path.cwd() / "alpine-usb-xfce.img"))
        self.device_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select image and USB device.")
        self.devices: list[tuple[str, str]] = []

        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        # Use classic Tk widgets with explicit colors. macOS dark-mode + old Tk
        # can render ttk text invisible, causing a blank window.
        bg = "#f3f4f6"
        fg = "#111827"
        panel = "#ffffff"
        pad = {"padx": 12, "pady": 7}

        tk.Label(self, text="Alpine USB XFCE Installer", font=("Helvetica", 20, "bold"), bg=bg, fg=fg).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(self, text="Flash a preconfigured Alpine Linux XFCE image to a USB drive. This erases the target drive.", bg=bg, fg=fg).pack(anchor="w", padx=14)

        frm = tk.Frame(self, bg=panel, highlightthickness=1, highlightbackground="#d1d5db")
        frm.pack(fill="x", padx=14, pady=12)

        tk.Label(frm, text="Image:", bg=panel, fg=fg).grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(frm, textvariable=self.image_var, bg="white", fg="black", insertbackground="black").grid(row=0, column=1, sticky="ew", padx=6, pady=7)
        tk.Button(frm, text="Browse", command=self.browse_image).grid(row=0, column=2, **pad)

        tk.Label(frm, text="USB device:", bg=panel, fg=fg).grid(row=1, column=0, sticky="w", **pad)
        self.combo = ttk.Combobox(frm, textvariable=self.device_var, state="readonly")
        self.combo.grid(row=1, column=1, sticky="ew", padx=6, pady=7)
        tk.Button(frm, text="Refresh", command=self.refresh_devices).grid(row=1, column=2, **pad)
        frm.columnconfigure(1, weight=1)

        tk.Label(self, text="WARNING: Flashing will permanently erase the selected USB device.", bg=bg, fg="#b91c1c", font=("Helvetica", 12, "bold")).pack(anchor="w", padx=14, pady=(0, 8))

        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", padx=14, pady=8)
        self.flash_btn = tk.Button(btns, text="Flash USB", command=self.confirm_flash, bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", padx=18, pady=8)
        self.flash_btn.pack(side="left")
        tk.Button(btns, text="Quit", command=self.destroy, padx=18, pady=8).pack(side="right")

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=14, pady=8)

        tk.Label(self, textvariable=self.status_var, bg=bg, fg=fg).pack(anchor="w", padx=14, pady=4)
        self.log = tk.Text(self, height=12, bg="#111827", fg="#e5e7eb", insertbackground="white")
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def log_line(self, text: str) -> None:
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def browse_image(self) -> None:
        path = filedialog.askopenfilename(title="Select image", filetypes=[("Disk images", "*.img *.raw *.iso"), ("All files", "*")])
        if path:
            self.image_var.set(path)

    def _tail_progress(self, log_path: str, last_pos: int, total_size: int, last_percent: int) -> tuple[int, int]:
        if not os.path.exists(log_path):
            return last_pos, last_percent
        with open(log_path, "r", errors="ignore") as fh:
            fh.seek(last_pos)
            data = fh.read()
            last_pos = fh.tell()
        for line in data.splitlines():
            self.log_line(line)
            m = re.search(r"(\d+) bytes", line)
            if m and total_size:
                percent = min(100, int(int(m.group(1)) * 100 / total_size))
                if percent != last_percent:
                    self.status_var.set(f"Flashing... {percent}%")
                    last_percent = percent
        return last_pos, last_percent

    def refresh_devices(self) -> None:
        self.devices = list_devices()
        labels = [label for _, label in self.devices]
        self.combo["values"] = labels
        if labels:
            self.combo.current(0)
            self.device_var.set(labels[0])
            self.status_var.set(f"Found {len(labels)} removable device(s).")
        else:
            self.device_var.set("")
            self.status_var.set("No removable USB devices found.")

    def selected_device(self) -> str | None:
        label = self.device_var.get()
        for dev, lab in self.devices:
            if lab == label:
                return dev
        return None

    def confirm_flash(self) -> None:
        image = Path(self.image_var.get())
        dev = self.selected_device()
        if not image.exists():
            messagebox.showerror(APP_TITLE, "Image file not found.")
            return
        if not dev:
            messagebox.showerror(APP_TITLE, "Select USB device.")
            return
        if not messagebox.askyesno(APP_TITLE, f"Erase and flash {dev}?\n\nImage: {image}\n\nThis cannot be undone."):
            return
        threading.Thread(target=self.flash, args=(str(image), dev), daemon=True).start()

    def flash(self, image: str, dev: str) -> None:
        self.flash_btn.config(state="disabled")
        self.progress.start(10)
        self.log_line(f"Flashing {image} -> {dev}")
        try:
            sys = platform.system()
            if sys == "Darwin":
                raw = dev.replace("/dev/disk", "/dev/rdisk")
                # macOS TCC can block root/osascript from reading files under
                # Documents/Desktop. Expose the image via a hard link in /tmp.
                # This does NOT copy the 16GB image or load it into RAM.
                tmp_image = os.path.join(tempfile.gettempdir(), "alpine-usb-xfce.img")
                try:
                    os.remove(tmp_image)
                except FileNotFoundError:
                    pass
                self.log_line(f"Linking image to temporary path: {tmp_image}")
                try:
                    os.link(image, tmp_image)
                except OSError as exc:
                    raise RuntimeError(
                        "Could not create hard link in /tmp. Move the image to /tmp "
                        "or grant Terminal/Python Full Disk Access, then retry. "
                        f"Details: {exc}"
                    )
                self.log_line("Unmounting disk...")
                subprocess.run(["diskutil", "unmountDisk", dev], check=True)
                log_path = os.path.join(tempfile.gettempdir(), "alpine-usb-flash.log")
                try:
                    os.remove(log_path)
                except FileNotFoundError:
                    pass
                size = os.path.getsize(tmp_image)
                # macOS dd has no status=progress. Send SIGINFO every 2s and
                # stream dd stderr from a temp log into the GUI.
                cmd = (
                    f"/bin/sh -c "
                    f"{sh_quote('( /bin/dd if=' + sh_quote(tmp_image) + ' of=' + sh_quote(raw) + ' bs=4m 2> ' + sh_quote(log_path) + '; echo __DD_DONE__$? >> ' + sh_quote(log_path) + '; /bin/sync; /usr/sbin/diskutil eject ' + sh_quote(dev) + ' >> ' + sh_quote(log_path) + ' 2>&1 ) & pid=$!; while kill -0 $pid 2>/dev/null; do kill -INFO $pid 2>/dev/null; sleep 2; done; wait $pid')}"
                )
                self.log_line("Requesting administrator permissions...")
                proc = subprocess.Popen(["osascript", "-e", f'do shell script {cmd!r} with administrator privileges'])
                last_pos = 0
                last_percent = -1
                while proc.poll() is None:
                    last_pos, last_percent = self._tail_progress(log_path, last_pos, size, last_percent)
                    self.after(0, self.update_idletasks)
                    threading.Event().wait(0.5)
                last_pos, last_percent = self._tail_progress(log_path, last_pos, size, last_percent)
                if proc.returncode:
                    raise subprocess.CalledProcessError(proc.returncode, proc.args)
            elif sys == "Linux":
                if os.geteuid() != 0:
                    sudo = shutil.which("pkexec") or shutil.which("sudo")
                    if not sudo:
                        raise RuntimeError("Need root privileges. Install pkexec or run with sudo.")
                    cmd = [sudo, "dd", f"if={image}", f"of={dev}", "bs=4M", "status=progress", "conv=fsync"]
                else:
                    cmd = ["dd", f"if={image}", f"of={dev}", "bs=4M", "status=progress", "conv=fsync"]
                subprocess.run(["umount", dev + "*"], shell=False, check=False)
                subprocess.run(cmd, check=True)
                subprocess.run(["sync"], check=True)
            else:
                raise RuntimeError("Windows raw flashing not implemented. Use Rufus/balenaEtcher with generated image.")
            self.log_line("Done. USB flashed and safe to remove.")
            self.status_var.set("Done.")
        except Exception as exc:
            self.log_line(f"ERROR: {exc}")
            self.status_var.set("Failed.")
        finally:
            self.progress.stop()
            self.flash_btn.config(state="normal")


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    App().mainloop()
