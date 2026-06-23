from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

SECTOR_SIZE = 512
MIN_RAW_IMAGE_SIZE = 16 * 1024 * 1024
ESP_TYPE_GUID = bytes.fromhex("28732ac11ff8d211ba4b00a0c93ec93b")
LINUX_TYPE_GUID = bytes.fromhex("af3dc60f838472478e793d69d8477de4")


@dataclass(frozen=True)
class ImageValidation:
    ok: bool
    reason: str | None = None
    size: int = 0
    esp_offset: int | None = None
    root_offset: int | None = None


def validate_usb_image(path: str | Path) -> ImageValidation:
    image = Path(path).expanduser()
    if not image.exists():
        return ImageValidation(False, f"Image not found: {image}")
    if not image.is_file():
        return ImageValidation(False, f"Image path is not a file: {image}")

    size = image.stat().st_size
    if size < MIN_RAW_IMAGE_SIZE:
        return ImageValidation(False, f"Image is too small to be a complete raw USB image: {size} bytes", size=size)

    try:
        with image.open("rb") as fh:
            fh.seek(SECTOR_SIZE)
            header = fh.read(SECTOR_SIZE)
            if len(header) != SECTOR_SIZE or header[:8] != b"EFI PART":
                return ImageValidation(False, "Image does not contain a valid GPT header", size=size)

            header_size = struct.unpack_from("<I", header, 12)[0]
            header_crc = struct.unpack_from("<I", header, 16)[0]
            current_lba = struct.unpack_from("<Q", header, 24)[0]
            backup_lba = struct.unpack_from("<Q", header, 32)[0]
            first_usable_lba = struct.unpack_from("<Q", header, 40)[0]
            last_usable_lba = struct.unpack_from("<Q", header, 48)[0]
            entries_lba = struct.unpack_from("<Q", header, 72)[0]
            num_entries = struct.unpack_from("<I", header, 80)[0]
            entry_size = struct.unpack_from("<I", header, 84)[0]
            entries_crc = struct.unpack_from("<I", header, 88)[0]

            total_sectors = size // SECTOR_SIZE
            if not (92 <= header_size <= SECTOR_SIZE):
                return ImageValidation(False, "GPT header size is invalid", size=size)
            header_for_crc = bytearray(header[:header_size])
            struct.pack_into("<I", header_for_crc, 16, 0)
            if zlib.crc32(header_for_crc) & 0xFFFFFFFF != header_crc:
                return ImageValidation(False, "GPT header checksum is invalid", size=size)
            if current_lba != 1:
                return ImageValidation(False, "GPT header is not at the expected LBA", size=size)
            if backup_lba >= total_sectors:
                return ImageValidation(
                    False, "Image appears truncated: GPT backup header is beyond end of file", size=size
                )
            if not (first_usable_lba < last_usable_lba < total_sectors):
                return ImageValidation(False, "GPT usable sector range is invalid", size=size)
            if num_entries <= 0 or entry_size < 128 or entry_size % 8 != 0:
                return ImageValidation(False, "GPT partition table metadata is invalid", size=size)

            entries_offset = entries_lba * SECTOR_SIZE
            entries_bytes = num_entries * entry_size
            if entries_offset + entries_bytes > size:
                return ImageValidation(
                    False, "Image appears truncated: GPT partition entries are incomplete", size=size
                )

            fh.seek(entries_offset)
            entries = fh.read(entries_bytes)
            if zlib.crc32(entries) & 0xFFFFFFFF != entries_crc:
                return ImageValidation(False, "GPT partition table checksum is invalid", size=size)
            fh.seek(backup_lba * SECTOR_SIZE)
            backup_header = fh.read(SECTOR_SIZE)
            if len(backup_header) != SECTOR_SIZE or backup_header[:8] != b"EFI PART":
                return ImageValidation(False, "GPT backup header is missing or incomplete", size=size)
            esp_offset = None
            root_offset = None
            root_last_lba = None

            for index in range(num_entries):
                entry = entries[index * entry_size : (index + 1) * entry_size]
                type_guid = entry[:16]
                if type_guid == b"\0" * 16:
                    continue
                first_lba = struct.unpack_from("<Q", entry, 32)[0]
                last_lba = struct.unpack_from("<Q", entry, 40)[0]
                if first_lba > last_lba or last_lba >= total_sectors:
                    return ImageValidation(
                        False, "Image appears truncated: a partition extends beyond end of file", size=size
                    )
                if type_guid == ESP_TYPE_GUID:
                    esp_offset = first_lba * SECTOR_SIZE
                elif type_guid == LINUX_TYPE_GUID and root_offset is None:
                    root_offset = first_lba * SECTOR_SIZE
                    root_last_lba = last_lba

            if esp_offset is None:
                return ImageValidation(False, "EFI System Partition not found in image", size=size)
            if root_offset is None or root_last_lba is None:
                return ImageValidation(
                    False, "Linux root partition not found in image", size=size, esp_offset=esp_offset
                )

            superblock_offset = root_offset + 1024
            if superblock_offset + 2048 > size:
                return ImageValidation(
                    False,
                    "Image appears truncated: root filesystem superblock is incomplete",
                    size=size,
                    esp_offset=esp_offset,
                    root_offset=root_offset,
                )
            fh.seek(superblock_offset)
            superblock = fh.read(2048)
            if superblock[0x38:0x3A] != b"\x53\xef":
                return ImageValidation(
                    False,
                    "Root partition does not look like an ext filesystem",
                    size=size,
                    esp_offset=esp_offset,
                    root_offset=root_offset,
                )
    except OSError as exc:
        return ImageValidation(False, f"Could not read image: {exc}", size=size)
    except struct.error as exc:
        return ImageValidation(False, f"Image metadata is corrupt: {exc}", size=size)

    return ImageValidation(True, size=size, esp_offset=esp_offset, root_offset=root_offset)
