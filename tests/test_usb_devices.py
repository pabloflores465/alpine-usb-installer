from __future__ import annotations

import plistlib
import subprocess

import pytest

from alpine_usb.usb_devices import detection


def completed_plist(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["diskutil"], 0, plistlib.dumps(payload).decode(), "")


def test_selected_device_strips_full_gui_label_to_raw_device_path() -> None:
    label = "/dev/disk20 (62.0 GB) DataTraveler 3.0 serial=disk20 — Volume: 0xEF"

    assert detection.selected_device(label) == "/dev/disk20"


@pytest.mark.parametrize("dev", ["/dev/disk2s1", "/dev/rdisk2s1", "/dev/sdb1", "/dev/nvme0n1p1", "/dev/mmcblk0p2"])
def test_looks_like_partition_detects_partition_paths(dev: str) -> None:
    assert detection.looks_like_partition(dev)


@pytest.mark.parametrize("dev", ["/dev/disk2", "/dev/rdisk2", "/dev/sdb", "/dev/nvme0n1", "/dev/mmcblk0"])
def test_looks_like_partition_allows_whole_disk_paths(dev: str) -> None:
    assert not detection.looks_like_partition(dev)


def test_format_size_bytes_uses_si_units() -> None:
    assert detection.format_size_bytes(None) == "unknown size"
    assert detection.format_size_bytes(999) == "999 B"
    assert detection.format_size_bytes(62_000_000_000) == "62.0 GB"


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"type": "disk", "rm": 1}, True),
        ({"type": "disk", "hotplug": 1}, True),
        ({"type": "disk", "tran": "usb"}, True),
        ({"type": "part", "rm": 1}, False),
        ({"type": "disk", "rm": 0, "hotplug": 0, "tran": "sata"}, False),
    ],
)
def test_linux_device_is_removable_disk(info: dict, expected: bool) -> None:
    assert detection.linux_device_is_removable_disk(info) is expected


def test_device_safety_report_accepts_external_macos_whole_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        detection,
        "run",
        lambda *args, **kwargs: completed_plist(
            {
                "Internal": False,
                "TotalSize": 62_000_000_000,
                "MediaName": "DataTraveler 3.0",
                "BusProtocol": "USB",
                "DeviceIdentifier": "disk20",
            }
        ),
    )

    ok, dev, rows, reason = detection.device_safety_report("/dev/disk20 (62.0 GB) DataTraveler")

    assert ok is True
    assert dev == "/dev/disk20"
    assert reason is None
    assert dict(rows)["Model/media"] == "DataTraveler 3.0"


def test_device_safety_report_rejects_internal_macos_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(detection, "run", lambda *args, **kwargs: completed_plist({"Internal": True}))

    ok, dev, _rows, reason = detection.device_safety_report("/dev/disk0")

    assert ok is False
    assert dev == "/dev/disk0"
    assert reason == "Refusing to flash internal disk: /dev/disk0"


def test_list_devices_on_linux_returns_only_removable_disks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        detection,
        "linux_lsblk_devices",
        lambda path=None: [
            {"path": "/dev/sda", "type": "disk", "rm": 0, "hotplug": 0, "tran": "sata", "size": 1},
            {
                "path": "/dev/sdb",
                "type": "disk",
                "rm": 1,
                "hotplug": 1,
                "tran": "usb",
                "size": 16_000_000_000,
                "model": "USB",
                "serial": "123",
            },
        ],
    )

    assert detection.list_devices() == [("/dev/sdb", "/dev/sdb (16.0 GB) USB serial=123")]


def test_list_devices_on_macos_keeps_full_label_but_returns_safe_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection.platform, "system", lambda: "Darwin")

    def fake_run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        if cmd[:2] == ["diskutil", "list"]:
            return completed_plist(
                {
                    "AllDisksAndPartitions": [
                        {
                            "DeviceIdentifier": "disk20",
                            "Partitions": [{"VolumeName": "ALPINE"}, {"Content": "0xEF"}],
                        }
                    ]
                }
            )
        return completed_plist(
            {
                "Internal": False,
                "TotalSize": 62_000_000_000,
                "MediaName": "DataTraveler 3.0",
                "DeviceIdentifier": "disk20",
            }
        )

    monkeypatch.setattr(detection, "run", fake_run)

    assert detection.list_devices() == [
        ("/dev/disk20", "/dev/disk20 (62.0 GB) DataTraveler 3.0 serial=disk20 — Volume: ALPINE, 0xEF")
    ]
