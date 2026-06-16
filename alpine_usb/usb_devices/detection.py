from __future__ import annotations

import json
import platform
import plistlib
import re
import subprocess


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, **kwargs)


def format_size_bytes(size: int | None) -> str:
    if not size:
        return "unknown size"
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1000 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1000
    return f"{int(value)} B"


def linux_lsblk_devices(path: str | None = None) -> list[dict]:
    cmd = ["lsblk", "-J", "-b", "-o", "PATH,NAME,SIZE,TRAN,TYPE,MODEL,SERIAL,RM,HOTPLUG"]
    if path:
        cmd.append(path)
    cp = run(cmd, capture_output=True)
    if cp.returncode != 0:
        return []
    try:
        return json.loads(cp.stdout).get("blockdevices", []) or []
    except Exception:
        return []


def linux_device_is_removable_disk(info: dict) -> bool:
    return info.get("type") == "disk" and (
        str(info.get("rm", "0")) == "1" or str(info.get("hotplug", "0")) == "1" or info.get("tran") == "usb"
    )


def selected_device(label: str) -> str | None:
    if label.startswith("/dev/"):
        return label.split()[0]
    match = re.match(r"(/dev/\S+)", label)
    return match.group(1) if match else None


def looks_like_partition(dev: str) -> bool:
    return bool(re.match(r"^/dev/(r?disk\d+s\d+|sd[a-z]\d+|nvme\d+n\d+p\d+|mmcblk\d+p\d+)", dev))


def normalize_disk_device(dev: str) -> str:
    if platform.system() == "Darwin" and dev.startswith("/dev/rdisk"):
        return dev.replace("/dev/rdisk", "/dev/disk", 1)
    return dev


def device_safety_report(dev: str) -> tuple[bool, str, list[tuple[str, str]], str | None]:
    dev = selected_device(dev) or dev
    sysname = platform.system()
    dev = normalize_disk_device(dev)
    rows: list[tuple[str, str]] = [("Target", dev)]
    if looks_like_partition(dev):
        return False, dev, rows, f"Use the whole disk, not a partition: {dev}"
    if sysname == "Darwin":
        if not re.match(r"^/dev/disk\d+$", dev):
            return False, dev, rows, "macOS target must be a whole disk like /dev/disk7"
        cp = run(["diskutil", "info", "-plist", dev], capture_output=True)
        if cp.returncode != 0:
            return False, dev, rows, f"Could not inspect target device: {dev}"
        try:
            meta = plistlib.loads(cp.stdout.encode())
        except Exception as exc:
            return False, dev, rows, f"Could not parse diskutil info for {dev}: {exc}"
        if bool(meta.get("Internal")):
            return False, dev, rows, f"Refusing to flash internal disk: {dev}"
        rows.extend(
            [
                ("Model/media", str(meta.get("MediaName") or meta.get("IORegistryEntryName") or "unknown")),
                ("Size", format_size_bytes(int(meta.get("TotalSize", 0) or 0))),
                ("Protocol", str(meta.get("BusProtocol") or meta.get("DeviceProtocol") or "unknown")),
                ("Serial/id", str(meta.get("DeviceIdentifier") or "unknown")),
            ]
        )
        return True, dev, rows, None
    if sysname == "Linux":
        infos = linux_lsblk_devices(dev)
        if not infos:
            return False, dev, rows, f"Could not inspect target device with lsblk: {dev}"
        info = infos[0]
        if not linux_device_is_removable_disk(info):
            return False, dev, rows, f"Refusing non-removable/non-hotplug disk: {dev}"
        rows.extend(
            [
                ("Model", str(info.get("model") or "unknown")),
                ("Size", format_size_bytes(int(info.get("size", 0) or 0))),
                ("Transport", str(info.get("tran") or "unknown")),
                ("Serial", str(info.get("serial") or "unknown")),
                ("RM/HOTPLUG", f"{info.get('rm', 0)}/{info.get('hotplug', 0)}"),
            ]
        )
        return True, dev, rows, None
    return False, dev, rows, "Windows flashing is not implemented. Use Rufus/balenaEtcher with the generated image."


def list_devices() -> list[tuple[str, str]]:
    sysname = platform.system()
    devices: list[tuple[str, str]] = []
    if sysname == "Darwin":
        cp = run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
        try:
            data = plistlib.loads(cp.stdout.encode())
            for disk in data.get("AllDisksAndPartitions", []):
                ident = disk.get("DeviceIdentifier")
                if not ident:
                    continue
                dev = f"/dev/{ident}"
                ok_safe, safe_dev, rows, _reason = device_safety_report(dev)
                if not ok_safe:
                    continue
                details = dict(rows)
                volumes = []
                for part in disk.get("Partitions", []) or []:
                    vol = part.get("VolumeName")
                    content = part.get("Content")
                    if vol and vol not in volumes:
                        volumes.append(vol)
                    elif content and content not in {"EFI", "Apple_partition_scheme"} and content not in volumes:
                        volumes.append(content)
                vol_text = f" — Volume: {', '.join(volumes)}" if volumes else ""
                label = f"{safe_dev} ({details.get('Size', 'unknown size')}) {details.get('Model/media', 'USB')} serial={details.get('Serial/id', 'unknown')}{vol_text}"
                devices.append((safe_dev, label))
        except Exception:
            pass
    elif sysname == "Linux":
        for info in linux_lsblk_devices():
            if not linux_device_is_removable_disk(info):
                continue
            path = info.get("path") or (f"/dev/{info.get('name')}" if info.get("name") else "")
            if not path:
                continue
            size = format_size_bytes(int(info.get("size", 0) or 0))
            model = str(info.get("model") or "USB")
            serial = str(info.get("serial") or "unknown")
            devices.append((path, f"{path} ({size}) {model} serial={serial}".strip()))
    return devices
