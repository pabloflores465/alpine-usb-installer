#!/usr/bin/env bash
# Build a preconfigured Alpine Linux USB image that boots straight to LightDM/XFCE.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-alpine-usb-xfce.img}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
ALPINE_BRANCH="${ALPINE_BRANCH:-latest-stable}"
ARCH="${ARCH:-x86_64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
MAKE_VM_IMAGE="$WORK_DIR/alpine-make-vm-image.uefi"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }

# macOS cannot run the Linux/NBD build natively. Always run it in a fresh
# privileged Docker container with the required build tools, and remove the
# container afterwards (--rm). This also makes the CLI behave like the GUI.
if [ "$(uname -s)" = "Darwin" ] && [ "${ALPINE_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Install Docker Desktop and try again." >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop and try again." >&2
    exit 1
  fi

  echo "Starting fresh Docker build container with Alpine build tools..."
  exec docker run --rm --platform linux/amd64 --privileged \
    -e ALPINE_USB_BUILD_IN_DOCKER=1 \
    -e IMAGE_NAME="$IMAGE_NAME" \
    -e IMAGE_SIZE="$IMAGE_SIZE" \
    -e ALPINE_BRANCH="$ALPINE_BRANCH" \
    -e ARCH="$ARCH" \
    -v "$SCRIPT_DIR:/work" \
    -w /work \
    alpine:latest \
    sh -ceu '
      apk add --no-cache bash curl sudo python3 e2fsprogs dosfstools util-linux sfdisk \
        multipath-tools qemu-img qemu-system-x86_64 parted grub grub-efi mtools \
        xorriso rsync kmod >/dev/null
      chmod +x build-alpine-usb.sh configure-alpine-usb.sh
      exec ./build-alpine-usb.sh
    '
fi

need curl
need sudo
need python3
need mmd
need mcopy

mkdir -p "$WORK_DIR"

if [ ! -x "$MAKE_VM_IMAGE" ]; then
  echo "Downloading alpine-make-vm-image..."
  curl -L "https://raw.githubusercontent.com/alpinelinux/alpine-make-vm-image/master/alpine-make-vm-image" -o "$MAKE_VM_IMAGE"
  chmod +x "$MAKE_VM_IMAGE"
fi

chmod +x "$SCRIPT_DIR/configure-alpine-usb.sh"

# Docker Desktop/macOS can be slow or unable to expose NBD partition nodes
# (/dev/nbdXp1, /dev/nbdXp2). Patch alpine-make-vm-image to force a partition
# re-read and fall back to kpartx mapper nodes (/dev/mapper/nbdXpN).
python3 - <<'PY'
from pathlib import Path
import re
p = Path('.work/alpine-make-vm-image.uefi')
s = p.read_text()

# Remove kpartx mappings before disconnecting NBD; otherwise qemu-nbd can fail.
s = s.replace('''\tif [ "$disk_dev" ] && ! [ -b "$IMAGE_FILE" ]; then\n\t\tqemu-nbd --disconnect "$disk_dev" \\\n\t\t\t|| die "Failed to disconnect $disk_dev; disconnect it manually"\n\tfi''', '''\tif [ "$disk_dev" ] && ! [ -b "$IMAGE_FILE" ]; then\n\t\tkpartx -d "$disk_dev" >/dev/null 2>&1 || true\n\t\tqemu-nbd --disconnect "$disk_dev" \\\n\t\t\t|| die "Failed to disconnect $disk_dev; disconnect it manually"\n\tfi''')

old = r'''\t# This is needed when running in a container(?:.|
)*?\tsettle_dev_node "\$root_dev" \|\| die "system didn't create \$root_dev node"'''
new = '''\t# This is needed when running in a container. Docker Desktop can be slow
\t# or unable to expose NBD partition nodes, so force a partition re-read.
\tpartprobe "$disk_dev" 2>/dev/null || true
\tblockdev --rereadpt "$disk_dev" 2>/dev/null || true
\tpartx -a "$disk_dev" 2>/dev/null || partx -u "$disk_dev" 2>/dev/null || true
\tfor i in $(seq 1 45); do
\t\tsettle_dev_node "$root_dev" && break
\t\tsleep 1
\tdone
\tif ! [ -e "$root_dev" ]; then
\t\t# Fallback for Docker Desktop: create /dev/mapper/nbdXpN nodes.
\t\tkpartx -avs "$disk_dev" || true
\t\tmapper_base="/dev/mapper/$(basename "$disk_dev")"
\t\tif [ "$BOOT_MODE" = 'BIOS' ]; then
\t\t\troot_dev="${mapper_base}p1"
\t\telse
\t\t\tesp_dev="${mapper_base}p1"
\t\t\troot_dev="${mapper_base}p2"
\t\tfi
\tfi
\tfor i in $(seq 1 20); do
\t\tsettle_dev_node "$root_dev" && break
\t\tsleep 1
\tdone
\tsettle_dev_node "$root_dev" || die "system didn't create $root_dev node"'''
s, n = re.subn(old, new, s, count=1)
if n != 1:
    raise SystemExit('Could not patch alpine-make-vm-image partition wait block')
p.write_text(s)
PY

install_uefi_removable_bootloader() {
  # Many real PCs only list USB media as bootable when the removable-media
  # fallback path exists. alpine-make-vm-image only creates startup.nsh plus
  # /grub/grub.cfg, which works in some EFI shells/QEMU but is not enough for
  # typical firmware boot menus.
  local image="$1"
  local fallback="$SCRIPT_DIR/efi-fallback/BOOTX64.EFI"
  local standalone_cfg="$SCRIPT_DIR/efi-fallback/grub-standalone.cfg"
  local esp_offset root_uuid image_meta grub_cfg

  image_meta="$(python3 - "$image" <<'PY'
import struct
import sys
import uuid

image = sys.argv[1]
esp_type = bytes.fromhex("28732ac11ff8d211ba4b00a0c93ec93b")    # C12A7328-F81F-11D2-BA4B-00A0C93EC93B
linux_type = bytes.fromhex("af3dc60f838472478e793d69d8477de4")  # 0FC63DAF-8483-4772-8E79-3D69D8477DE4
sector = 512
esp_offset = None
root_offset = None

with open(image, "rb") as f:
    f.seek(sector)
    header = f.read(sector)
    if header[:8] != b"EFI PART":
        raise SystemExit("Image does not contain a GPT header")
    entries_lba = struct.unpack_from("<Q", header, 72)[0]
    num_entries = struct.unpack_from("<I", header, 80)[0]
    entry_size = struct.unpack_from("<I", header, 84)[0]
    f.seek(entries_lba * sector)
    for _ in range(num_entries):
        entry = f.read(entry_size)
        first_lba = struct.unpack_from("<Q", entry, 32)[0]
        if entry[:16] == esp_type:
            esp_offset = first_lba * sector
        elif entry[:16] == linux_type and root_offset is None:
            root_offset = first_lba * sector
    if esp_offset is None:
        raise SystemExit("EFI System Partition not found")
    if root_offset is None:
        raise SystemExit("Linux root partition not found")
    f.seek(root_offset + 1024)
    superblock = f.read(2048)
    if superblock[0x38:0x3a] != b"\x53\xef":
        raise SystemExit("Root partition does not look like ext2/3/4")
    root_uuid = uuid.UUID(bytes=superblock[0x68:0x78])

print(f"esp_offset={esp_offset}")
print(f"root_uuid={root_uuid}")
PY
)"
  eval "$image_meta"

  grub_cfg="$WORK_DIR/grub-usb.cfg"
  mkdir -p "$SCRIPT_DIR/efi-fallback"
  cat > "$grub_cfg" <<EOF
set default=0
set timeout=3
set timeout_style=menu

insmod part_gpt
insmod fat
insmod gzio
insmod linux
insmod search_fs_file
search --no-floppy --file --set=root /vmlinuz-lts

menuentry 'Alpine Linux XFCE (LightDM)' {
    linux /vmlinuz-lts root=UUID=$root_uuid ro rootfstype=ext4 rootwait rootdelay=5 modules=ata,base,ext4,kms,mmc,nvme,scsi,usb,virtio console=tty0
    initrd /initramfs-lts
}

menuentry 'Alpine Linux XFCE (safe graphics)' {
    linux /vmlinuz-lts root=UUID=$root_uuid ro rootfstype=ext4 rootwait rootdelay=5 modules=ata,base,ext4,kms,mmc,nvme,scsi,usb,virtio console=tty0 nomodeset
    initrd /initramfs-lts
}
EOF

  need grub-mkstandalone
  cat > "$standalone_cfg" <<EOF
insmod part_gpt
insmod fat
insmod search_fs_file
search --no-floppy --file --set=esp /grub/grub.cfg
# Keep prefix on the standalone memdisk so GRUB can load embedded modules.
# If prefix points to the USB ESP, GRUB looks for /grub/x86_64-efi/*.mod there.
set prefix=(memdisk)/boot/grub
configfile (\$esp)/grub/grub.cfg

$(cat "$grub_cfg")
EOF
  grub-mkstandalone \
    -O x86_64-efi \
    --modules="part_gpt fat gzio linux search_fs_file configfile normal" \
    -o "$fallback" \
    "boot/grub/grub.cfg=$standalone_cfg"

  mmd -i "${image}@@${esp_offset}" ::/EFI >/dev/null 2>&1 || true
  mmd -i "${image}@@${esp_offset}" ::/EFI/BOOT >/dev/null 2>&1 || true
  mmd -i "${image}@@${esp_offset}" ::/grub >/dev/null 2>&1 || true
  mcopy -o -i "${image}@@${esp_offset}" "$fallback" ::/EFI/BOOT/BOOTX64.EFI
  mcopy -o -i "${image}@@${esp_offset}" "$grub_cfg" ::/grub/grub.cfg
  echo "Installed removable UEFI bootloader: /EFI/BOOT/BOOTX64.EFI"
  echo "Installed USB GRUB config: /grub/grub.cfg (root UUID $root_uuid)"
}

cat > "$SCRIPT_DIR/repositories" <<EOF
https://dl-cdn.alpinelinux.org/alpine/$ALPINE_BRANCH/main
https://dl-cdn.alpinelinux.org/alpine/$ALPINE_BRANCH/community
EOF

cd "$SCRIPT_DIR"

# Always rebuild from a clean image. Reusing an old raw image can leave stale
# filesystem signatures and confuse NBD partition node creation.
rm -f "$SCRIPT_DIR/$IMAGE_NAME"

# raw image: easiest to dd to USB. serial console kept useful for debug; graphical boot still LightDM.
sudo "$MAKE_VM_IMAGE" \
  --image-format raw \
  --image-size "$IMAGE_SIZE" \
  --arch "$ARCH" \
  --boot-mode UEFI \
  --initfs-features "ata base ext4 kms mmc nvme scsi usb virtio" \
  --repositories-file "$SCRIPT_DIR/repositories" \
  --script-chroot \
  "$SCRIPT_DIR/$IMAGE_NAME" \
  "$SCRIPT_DIR/configure-alpine-usb.sh"

install_uefi_removable_bootloader "$SCRIPT_DIR/$IMAGE_NAME"

cat <<EOF

DONE: $SCRIPT_DIR/$IMAGE_NAME

Write to USB:
  lsblk
  sudo dd if="$SCRIPT_DIR/$IMAGE_NAME" of=/dev/sdX bs=4M status=progress conv=fsync

Replace /dev/sdX with USB device, not partition. Example /dev/sdb, NOT /dev/sdb1.

First boot:
  graphical LightDM should start.
  user: pablo
  pass: pablo
  run: passwd
EOF
