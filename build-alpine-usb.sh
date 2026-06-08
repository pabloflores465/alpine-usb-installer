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

need curl
need sudo

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
