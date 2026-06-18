#!/usr/bin/env bash
# Build a configurable, preinstalled Debian Linux USB image.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-debian-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
DEBIAN_RELEASE="${DEBIAN_RELEASE:-stable}"
ARCH="${ARCH:-amd64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
ROOTFS="$WORK_DIR/debian-rootfs"
IMAGE_PATH="$SCRIPT_DIR/$IMAGE_NAME"
DEBIAN_MIRROR="${DEBIAN_MIRROR:-http://deb.debian.org/debian}"
DOCKER_IMAGE="${DEBIAN_USB_DOCKER_IMAGE:-debian:stable-slim}"

case "$DEBIAN_RELEASE" in stable|testing|sid|bookworm|trixie|forky) ;; *) echo "Invalid Debian release: $DEBIAN_RELEASE" >&2; exit 1 ;; esac
case "$ARCH" in amd64|x86_64) ARCH="amd64" ;; *) echo "Only amd64/x86_64 is supported for Debian builds" >&2; exit 1 ;; esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid image name: $IMAGE_NAME" >&2; exit 1
fi
if [ -n "$OUTPUT_PATH" ]; then case "$OUTPUT_PATH" in /*) ;; *) echo "OUTPUT_PATH must be absolute: $OUTPUT_PATH" >&2; exit 1 ;; esac; fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
run_sudo() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }
cleanup_mounts() {
  set +e
  if mountpoint -q "$ROOTFS/dev/pts"; then run_sudo umount "$ROOTFS/dev/pts"; fi
  for mp in dev proc sys; do if mountpoint -q "$ROOTFS/$mp"; then run_sudo umount "$ROOTFS/$mp"; fi; done
  if [ -n "${LOOPDEV:-}" ]; then run_sudo losetup -d "$LOOPDEV"; fi
}
trap cleanup_mounts EXIT

if [ "$(uname -s)" = "Darwin" ] && [ "${DEBIAN_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  pass_env=(IMAGE_NAME OUTPUT_PATH IMAGE_SIZE DEBIAN_RELEASE ARCH DEBIAN_MIRROR DEBIAN_USB_USER DEBIAN_USB_PASSWORD_FILE DEBIAN_USB_ROOT_PASSWORD_FILE DEBIAN_USB_HOSTNAME DEBIAN_USB_TIMEZONE DEBIAN_USB_LOCALE DEBIAN_USB_LANGUAGE DEBIAN_USB_CONSOLE_KEYMAP DEBIAN_USB_XKB_LAYOUT DEBIAN_USB_XKB_VARIANT DEBIAN_USB_XKB_MODEL DEBIAN_USB_DESKTOP DEBIAN_USB_TILING_WMS DEBIAN_USB_DEFAULT_SESSION DEBIAN_USB_DISPLAY_MANAGER DEBIAN_USB_NETWORK DEBIAN_USB_WIFI DEBIAN_USB_BLUETOOTH DEBIAN_USB_AUDIO DEBIAN_USB_BROWSER DEBIAN_USB_FIRMWARE DEBIAN_USB_LEGACY_X11_DRIVERS DEBIAN_USB_BOOTLOADER DEBIAN_USB_KERNEL_FLAVOR DEBIAN_USB_BOOT_TIMEOUT DEBIAN_USB_AUTO_RESIZE DEBIAN_USB_EXTRA_PACKAGES DEBIAN_USB_PROFILE ALPINE_USB_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD_FILE)
  docker_env=(-e DEBIAN_USB_BUILD_IN_DOCKER=1)
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  for name in "${pass_env[@]}"; do
    value="${!name-}"
    if [ "$name" = "OUTPUT_PATH" ] && [ -n "$value" ]; then
      mkdir -p "$(dirname "$value")"; output_dir="$(cd "$(dirname "$value")" && pwd -P)"; output_base="$(basename "$value")"
      docker_mounts+=( -v "$output_dir:/out" ); docker_env+=( -e "OUTPUT_PATH=/out/$output_base" ); continue
    fi
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then value="/work/${value#"$SCRIPT_DIR"/}"; fi
    docker_env+=( -e "$name=$value" )
  done
  exec docker run --rm --platform linux/amd64 --privileged "${docker_env[@]}" "${docker_mounts[@]}" -w /work "$DOCKER_IMAGE" sh -ceu '
    apt-get update >/dev/null
    apt-get install -y --no-install-recommends bash ca-certificates debootstrap dosfstools e2fsprogs fdisk grub-efi-amd64-bin mtools parted util-linux xz-utils >/dev/null
    chmod +x build-debian-usb.sh configure-debian-usb.sh
    exec ./build-debian-usb.sh
  '
fi

need debootstrap; need parted; need losetup; need mkfs.vfat; need mkfs.ext4; need grub-install
mkdir -p "$WORK_DIR"; chmod 700 "$WORK_DIR" 2>/dev/null || true
rm -rf "$ROOTFS"
rm -f "$IMAGE_PATH"
truncate -s "$IMAGE_SIZE" "$IMAGE_PATH"
parted -s "$IMAGE_PATH" mklabel gpt mkpart ESP fat32 1MiB 513MiB set 1 esp on mkpart root ext4 513MiB 100%
LOOPDEV="$(run_sudo losetup --find --partscan --show "$IMAGE_PATH")"
sleep 1
EFI_PART="${LOOPDEV}p1"; ROOT_PART="${LOOPDEV}p2"
if [ ! -b "$EFI_PART" ]; then EFI_PART="${LOOPDEV}1"; ROOT_PART="${LOOPDEV}2"; fi
run_sudo mkfs.vfat -F32 -n DEBIANUSBEFI "$EFI_PART"
run_sudo mkfs.ext4 -F -L DEBIANUSBROOT "$ROOT_PART"
mkdir -p "$ROOTFS"
run_sudo mount "$ROOT_PART" "$ROOTFS"
run_sudo mkdir -p "$ROOTFS/boot/efi"
run_sudo mount "$EFI_PART" "$ROOTFS/boot/efi"
run_sudo debootstrap --arch="$ARCH" "$DEBIAN_RELEASE" "$ROOTFS" "$DEBIAN_MIRROR"
for mp in proc sys dev; do run_sudo mount --bind "/$mp" "$ROOTFS/$mp"; done
run_sudo mount --bind /dev/pts "$ROOTFS/dev/pts"
ROOT_UUID="$(blkid -s UUID -o value "$ROOT_PART")"
EFI_UUID="$(blkid -s UUID -o value "$EFI_PART")"
cat >"$WORK_DIR/fstab" <<EOF
UUID=$ROOT_UUID / ext4 defaults,noatime 0 1
UUID=$EFI_UUID /boot/efi vfat umask=0077 0 1
EOF
run_sudo cp "$WORK_DIR/fstab" "$ROOTFS/etc/fstab"
run_sudo cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf" 2>/dev/null || true
run_sudo env DEBIAN_USB_ROOT_MOUNT="$ROOTFS" ./configure-debian-usb.sh
run_sudo chroot "$ROOTFS" grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=debian-usb --removable --recheck
run_sudo chroot "$ROOTFS" update-grub
cleanup_mounts
trap - EXIT
if [ -n "$OUTPUT_PATH" ]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; mv "$IMAGE_PATH" "$OUTPUT_PATH"; echo "Image ready: $OUTPUT_PATH"; else echo "Image ready: $IMAGE_PATH"; fi
