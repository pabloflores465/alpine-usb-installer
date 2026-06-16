from __future__ import annotations

import struct
import zlib
from pathlib import Path

from alpine_usb.images.validation import ESP_TYPE_GUID, LINUX_TYPE_GUID, SECTOR_SIZE, validate_usb_image


def write_valid_image(path: Path, truncate_to: int | None = None) -> None:
    sectors = 40960
    size = sectors * SECTOR_SIZE
    data = bytearray(size)
    header = bytearray(SECTOR_SIZE)
    header[:8] = b"EFI PART"
    struct.pack_into("<I", header, 12, 92)
    struct.pack_into("<Q", header, 24, 1)
    struct.pack_into("<Q", header, 32, sectors - 1)
    struct.pack_into("<Q", header, 40, 34)
    struct.pack_into("<Q", header, 48, sectors - 34)
    struct.pack_into("<Q", header, 72, 2)
    struct.pack_into("<I", header, 80, 128)
    struct.pack_into("<I", header, 84, 128)

    entries = bytearray(128 * 128)
    entries[0:16] = ESP_TYPE_GUID
    struct.pack_into("<Q", entries, 32, 2048)
    struct.pack_into("<Q", entries, 40, 4095)
    offset = 128
    entries[offset : offset + 16] = LINUX_TYPE_GUID
    struct.pack_into("<Q", entries, offset + 32, 4096)
    struct.pack_into("<Q", entries, offset + 40, sectors - 2048)

    entries_crc = zlib.crc32(entries) & 0xFFFFFFFF
    struct.pack_into("<I", header, 88, entries_crc)
    header_for_crc = bytearray(header[:92])
    struct.pack_into("<I", header_for_crc, 16, 0)
    struct.pack_into("<I", header, 16, zlib.crc32(header_for_crc) & 0xFFFFFFFF)
    data[SECTOR_SIZE : SECTOR_SIZE * 2] = header
    data[SECTOR_SIZE * 2 : SECTOR_SIZE * 2 + len(entries)] = entries

    backup_header = bytearray(header)
    struct.pack_into("<Q", backup_header, 24, sectors - 1)
    struct.pack_into("<Q", backup_header, 32, 1)
    backup_for_crc = bytearray(backup_header[:92])
    struct.pack_into("<I", backup_for_crc, 16, 0)
    struct.pack_into("<I", backup_header, 16, zlib.crc32(backup_for_crc) & 0xFFFFFFFF)
    data[(sectors - 1) * SECTOR_SIZE : sectors * SECTOR_SIZE] = backup_header

    root_superblock = 4096 * SECTOR_SIZE + 1024
    data[root_superblock + 0x38 : root_superblock + 0x3A] = b"\x53\xef"

    if truncate_to is not None:
        data = data[:truncate_to]
    path.write_bytes(data)


def test_validate_usb_image_accepts_complete_raw_gpt_ext_image(tmp_path: Path) -> None:
    image = tmp_path / "alpine.img"
    write_valid_image(image)

    result = validate_usb_image(image)

    assert result.ok is True
    assert result.reason is None
    assert result.esp_offset == 2048 * SECTOR_SIZE
    assert result.root_offset == 4096 * SECTOR_SIZE


def test_validate_usb_image_rejects_missing_file(tmp_path: Path) -> None:
    result = validate_usb_image(tmp_path / "missing.img")

    assert result.ok is False
    assert result.reason and "Image not found" in result.reason


def test_validate_usb_image_rejects_too_small_file(tmp_path: Path) -> None:
    image = tmp_path / "tiny.img"
    image.write_bytes(b"not an image")

    result = validate_usb_image(image)

    assert result.ok is False
    assert result.reason and "too small" in result.reason


def test_validate_usb_image_rejects_corrupt_gpt(tmp_path: Path) -> None:
    image = tmp_path / "corrupt.img"
    image.write_bytes(b"\0" * (20 * 1024 * 1024))

    result = validate_usb_image(image)

    assert result.ok is False
    assert result.reason == "Image does not contain a valid GPT header"


def test_validate_usb_image_rejects_truncated_partition(tmp_path: Path) -> None:
    image = tmp_path / "truncated.img"
    write_valid_image(image, truncate_to=18 * 1024 * 1024)

    result = validate_usb_image(image)

    assert result.ok is False
    assert result.reason and "beyond end of file" in result.reason


def test_validate_usb_image_rejects_bad_partition_table_checksum(tmp_path: Path) -> None:
    image = tmp_path / "bad-checksum.img"
    write_valid_image(image)
    with image.open("r+b") as fh:
        fh.seek(SECTOR_SIZE * 2 + 32)
        fh.write(b"\0" * 8)

    result = validate_usb_image(image)

    assert result.ok is False
    assert result.reason == "GPT partition table checksum is invalid"


def test_validate_usb_image_rejects_missing_ext_superblock(tmp_path: Path) -> None:
    image = tmp_path / "bad-root.img"
    write_valid_image(image)
    data = bytearray(image.read_bytes())
    root_superblock = 4096 * SECTOR_SIZE + 1024
    data[root_superblock + 0x38 : root_superblock + 0x3A] = b"\0\0"
    image.write_bytes(data)

    result = validate_usb_image(image)

    assert result.ok is False
    assert result.reason == "Root partition does not look like an ext filesystem"
