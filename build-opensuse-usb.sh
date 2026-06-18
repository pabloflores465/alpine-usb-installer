#!/usr/bin/env bash
# Experimental openSUSE image builder foundation. Uses zypper --root when run on Linux with required privileges/tools.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-opensuse-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work/opensuse}"
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
[[ "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ && "$IMAGE_NAME" != .*..* && "$IMAGE_NAME" != */* ]] || { echo "Invalid image name: $IMAGE_NAME" >&2; exit 1; }
if [ "$(uname -s)" != Linux ]; then echo "openSUSE builds require Linux with zypper/loop tools; use --dry-run on this host." >&2; exit 1; fi
need zypper; need qemu-img; need parted; need mkfs.ext4; need grub2-install
mkdir -p "$WORK_DIR"
OPENSUSE_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-opensuse-usb.sh"
packages="${OPENSUSE_USB_PACKAGE_PLAN:-}"
[ -n "$packages" ] || packages="$({ OPENSUSE_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-opensuse-usb.sh" | sed -n 's/^Packages://p'; })"
image="$SCRIPT_DIR/$IMAGE_NAME"
root="$WORK_DIR/rootfs"
rm -rf "$root" "$image"
mkdir -p "$root"
qemu-img create -f raw "$image" "$IMAGE_SIZE"
echo "Created raw image skeleton: $image"
echo "Installing openSUSE package root with zypper --root (boot partitioning/fstab/grub finalization is experimental)."
zypper --non-interactive --root "$root" ar -f "https://download.opensuse.org/tumbleweed/repo/oss" oss
zypper --non-interactive --root "$root" --gpg-auto-import-keys refresh
# shellcheck disable=SC2086
zypper --non-interactive --root "$root" install --no-recommends $packages
cat > "$root/etc/hostname" <<<"${OPENSUSE_USB_HOSTNAME:-opensuse-usb}"
if [ -n "$OUTPUT_PATH" ]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; mv "$image" "$OUTPUT_PATH"; fi
echo "openSUSE rootfs populated. Full bootable-image finalization remains experimental; validate before flashing."
