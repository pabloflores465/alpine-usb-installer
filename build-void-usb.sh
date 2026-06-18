#!/usr/bin/env bash
# Build a configurable, preinstalled Void Linux USB image with xbps-install -r.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-void-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
VOID_REPOSITORY="${VOID_REPOSITORY:-${ALPINE_BRANCH:-current}}"
ARCH="${ARCH:-x86_64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
ROOT_DIR="$WORK_DIR/void-rootfs"
MOUNT_DIR="$WORK_DIR/void-mnt"
IMAGE_PATH="$SCRIPT_DIR/$IMAGE_NAME"

case "$ARCH" in x86_64) ;; *) echo "Void backend currently supports glibc x86_64 only" >&2; exit 1 ;; esac
case "$VOID_REPOSITORY" in current|glibc) REPO_URL="https://repo-default.voidlinux.org/current" ;; http://*|https://*|file://*) REPO_URL="${VOID_REPOSITORY%/}" ;; *) echo "Invalid Void repository: $VOID_REPOSITORY" >&2; exit 1 ;; esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then echo "Invalid image name: $IMAGE_NAME" >&2; exit 1; fi
if [ -n "$OUTPUT_PATH" ]; then case "$OUTPUT_PATH" in /*) ;; *) echo "OUTPUT_PATH must be absolute: $OUTPUT_PATH" >&2; exit 1 ;; esac; fi
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
for tool in xbps-install xbps-reconfigure qemu-img parted mkfs.vfat mkfs.ext4 mount umount blkid; do need "$tool"; done
if [ "$(uname -s)" = "Darwin" ]; then echo "Void image builds require native Linux for loop mounts; use a Linux VM/container." >&2; exit 1; fi
if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "Void image build must run as root (xbps-install -r + loop mounts)." >&2; exit 1; fi

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR" 2>/dev/null || true
rm -rf "$ROOT_DIR" "$MOUNT_DIR"
mkdir -p "$ROOT_DIR" "$MOUNT_DIR"
rm -f "$IMAGE_PATH"
qemu-img create -f raw "$IMAGE_PATH" "$IMAGE_SIZE"
parted -s "$IMAGE_PATH" mklabel gpt
parted -s "$IMAGE_PATH" mkpart ESP fat32 1MiB 513MiB
parted -s "$IMAGE_PATH" set 1 esp on
parted -s "$IMAGE_PATH" mkpart root ext4 513MiB 100%
LOOP="$(losetup --find --partscan --show "$IMAGE_PATH")"
cleanup() { set +e; mountpoint -q "$MOUNT_DIR/boot/efi" && umount "$MOUNT_DIR/boot/efi"; mountpoint -q "$MOUNT_DIR" && umount "$MOUNT_DIR"; [ -n "${LOOP:-}" ] && losetup -d "$LOOP"; }
trap cleanup EXIT
sleep 1
mkfs.vfat -F32 "${LOOP}p1"
mkfs.ext4 -F "${LOOP}p2"
mount "${LOOP}p2" "$MOUNT_DIR"
mkdir -p "$MOUNT_DIR/boot/efi"
mount "${LOOP}p1" "$MOUNT_DIR/boot/efi"

XBPS_ARCH="$ARCH" xbps-install -Sy -R "$REPO_URL" -r "$MOUNT_DIR" base-system xbps grub-x86_64-efi efibootmgr bash
for fs in dev proc sys run; do mount --rbind "/$fs" "$MOUNT_DIR/$fs"; done
cleanup_chroot_binds() { set +e; for fs in run sys proc dev; do mountpoint -q "$MOUNT_DIR/$fs" && umount -R "$MOUNT_DIR/$fs"; done; }
trap 'cleanup_chroot_binds; cleanup' EXIT
cp "$SCRIPT_DIR/configure-void-usb.sh" "$MOUNT_DIR/root/configure-void-usb.sh"
chmod +x "$MOUNT_DIR/root/configure-void-usb.sh"
chroot "$MOUNT_DIR" /root/configure-void-usb.sh
xbps-reconfigure -r "$MOUNT_DIR" -fa
ROOT_UUID="$(blkid -s UUID -o value "${LOOP}p2")"
mkdir -p "$MOUNT_DIR/boot/grub"
cat > "$MOUNT_DIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=${ALPINE_USB_BOOT_TIMEOUT:-3}
menuentry 'Void Linux USB' {
    linux /boot/vmlinuz root=UUID=$ROOT_UUID ro rootwait
    initrd /boot/initramfs
}
EOF
chroot "$MOUNT_DIR" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=VoidUSB --removable --recheck
cleanup_chroot_binds
umount "$MOUNT_DIR/boot/efi"
umount "$MOUNT_DIR"
losetup -d "$LOOP"
LOOP=""
if [ -n "$OUTPUT_PATH" ]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; mv "$IMAGE_PATH" "$OUTPUT_PATH"; fi
printf 'Void USB image ready: %s\n' "${OUTPUT_PATH:-$IMAGE_PATH}"
