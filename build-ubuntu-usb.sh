#!/usr/bin/env bash
# Build a configurable, preinstalled Ubuntu USB image.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-ubuntu-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
UBUNTU_RELEASE="${UBUNTU_RELEASE:-24.04}"
ARCH="${ARCH:-x86_64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
UBUNTU_MIRROR="${UBUNTU_MIRROR:-http://archive.ubuntu.com/ubuntu}"

case "$UBUNTU_RELEASE" in 24.04|noble) CODENAME="noble" ;; 22.04|jammy) CODENAME="jammy" ;; *) echo "Invalid Ubuntu release: $UBUNTU_RELEASE" >&2; exit 1 ;; esac
case "$ARCH" in x86_64|amd64) DEBOOTSTRAP_ARCH="amd64" ;; *) echo "Unsupported Ubuntu arch: $ARCH" >&2; exit 1 ;; esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid image name: $IMAGE_NAME" >&2
  exit 1
fi
if [ -n "$OUTPUT_PATH" ]; then
  case "$OUTPUT_PATH" in /*) ;; *) echo "OUTPUT_PATH must be absolute: $OUTPUT_PATH" >&2; exit 1 ;; esac
fi
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
read_secret_value() {
  local file_var="$1"
  local value_var="$2"
  local file_value="${!file_var:-}"
  local direct_value="${!value_var:-}"
  local default_value="$3"
  if [ -n "$file_value" ]; then
    cat "$file_value"
  elif [ -n "$direct_value" ]; then
    printf '%s' "$direct_value"
  else
    printf '%s' "$default_value"
  fi
}

if [ "$(uname -s)" = "Darwin" ] && [ "${UBUNTU_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  docker_env=(-e UBUNTU_USB_BUILD_IN_DOCKER=1 -e IMAGE_NAME="$IMAGE_NAME" -e IMAGE_SIZE="$IMAGE_SIZE" -e UBUNTU_RELEASE="$UBUNTU_RELEASE" -e ARCH="$ARCH")
  pass_env=(UBUNTU_USB_USER UBUNTU_USB_PASSWORD_FILE UBUNTU_USB_ROOT_PASSWORD_FILE UBUNTU_USB_HOSTNAME UBUNTU_USB_TIMEZONE UBUNTU_USB_LOCALE UBUNTU_USB_LANGUAGE UBUNTU_USB_CONSOLE_KEYMAP UBUNTU_USB_XKB_LAYOUT UBUNTU_USB_XKB_VARIANT UBUNTU_USB_XKB_MODEL UBUNTU_USB_DESKTOP UBUNTU_USB_TILING_WMS UBUNTU_USB_DEFAULT_SESSION UBUNTU_USB_DISPLAY_MANAGER UBUNTU_USB_NETWORK UBUNTU_USB_WIFI UBUNTU_USB_BLUETOOTH UBUNTU_USB_AUDIO UBUNTU_USB_BROWSER UBUNTU_USB_FIRMWARE UBUNTU_USB_LEGACY_X11_DRIVERS UBUNTU_USB_BOOTLOADER UBUNTU_USB_KERNEL_FLAVOR UBUNTU_USB_BOOT_TIMEOUT UBUNTU_USB_SYSTEMD_BOOT_CONSOLE_MODE UBUNTU_USB_AUTO_RESIZE UBUNTU_USB_EXTRA_PACKAGES UBUNTU_USB_PROFILE)
  for name in "${pass_env[@]}"; do docker_env+=( -e "$name=${!name-}" ); done
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  if [ -n "$OUTPUT_PATH" ]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; docker_mounts+=( -v "$(dirname "$OUTPUT_PATH"):/out" ); docker_env+=( -e "OUTPUT_PATH=/out/$(basename "$OUTPUT_PATH")" ); fi
  exec docker run --rm --platform linux/amd64 --privileged "${docker_env[@]}" "${docker_mounts[@]}" -w /work ubuntu:24.04 bash -ceu '
    apt-get update >/dev/null
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bash debootstrap gdisk parted dosfstools e2fsprogs util-linux grub-efi-amd64-bin grub-pc-bin mtools rsync sudo >/dev/null
    chmod +x build-ubuntu-usb.sh configure-ubuntu-usb.sh
    exec ./build-ubuntu-usb.sh
  '
fi

need sudo
need debootstrap
need sgdisk
need mkfs.vfat
need mkfs.ext4
need losetup
need partprobe
need chroot
need rsync
need grub-install

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/configure-ubuntu-usb.sh"

# Validate and show the package set before destructive loop-device work.
UBUNTU_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-ubuntu-usb.sh" >/dev/null

IMAGE_PATH="$SCRIPT_DIR/$IMAGE_NAME"
ROOT_DIR="$WORK_DIR/ubuntu-root-$CODENAME"
MNT_DIR="$WORK_DIR/ubuntu-mnt-$CODENAME"
rm -rf "$ROOT_DIR" "$MNT_DIR"
mkdir -p "$ROOT_DIR" "$MNT_DIR"
rm -f "$IMAGE_PATH"
truncate -s "$IMAGE_SIZE" "$IMAGE_PATH"
sgdisk --zap-all "$IMAGE_PATH" >/dev/null
sgdisk -n 1:1MiB:+512MiB -t 1:EF00 -c 1:EFI -n 2:0:0 -t 2:8300 -c 2:rootfs "$IMAGE_PATH" >/dev/null

LOOP="$(sudo losetup --find --show --partscan "$IMAGE_PATH")"
cleanup() {
  set +e
  sudo umount "$MNT_DIR/boot/efi" >/dev/null 2>&1
  sudo umount "$MNT_DIR/dev/pts" "$MNT_DIR/dev" "$MNT_DIR/proc" "$MNT_DIR/sys" >/dev/null 2>&1
  sudo umount "$MNT_DIR" >/dev/null 2>&1
  sudo losetup -d "$LOOP" >/dev/null 2>&1
}
trap cleanup EXIT
sudo partprobe "$LOOP" || true
sleep 1
ESP="${LOOP}p1"; ROOT="${LOOP}p2"
if [ ! -b "$ESP" ]; then ESP="/dev/mapper/$(basename "$LOOP")p1"; ROOT="/dev/mapper/$(basename "$LOOP")p2"; fi
sudo mkfs.vfat -F32 -n EFI "$ESP" >/dev/null
sudo mkfs.ext4 -F -L ubuntu-usb "$ROOT" >/dev/null
sudo mount "$ROOT" "$MNT_DIR"
sudo mkdir -p "$MNT_DIR/boot/efi"
sudo mount "$ESP" "$MNT_DIR/boot/efi"
sudo debootstrap --arch="$DEBOOTSTRAP_ARCH" --variant=minbase "$CODENAME" "$MNT_DIR" "$UBUNTU_MIRROR"
for fs in dev proc sys; do sudo mount --bind "/$fs" "$MNT_DIR/$fs"; done
sudo mount --bind /dev/pts "$MNT_DIR/dev/pts"

sudo UBUNTU_USB_TARGET_ROOT="$MNT_DIR" "$SCRIPT_DIR/configure-ubuntu-usb.sh"
CHROOT_USER="${UBUNTU_USB_USER:-ubuntu}"
CHROOT_PASSWORD="$(read_secret_value UBUNTU_USB_PASSWORD_FILE UBUNTU_USB_PASSWORD ubuntu)"
CHROOT_ROOT_PASSWORD="$(read_secret_value UBUNTU_USB_ROOT_PASSWORD_FILE UBUNTU_USB_ROOT_PASSWORD "$CHROOT_PASSWORD")"
sudo chroot "$MNT_DIR" /usr/bin/env \
  UBUNTU_USB_USER="$CHROOT_USER" \
  UBUNTU_USB_PASSWORD="$CHROOT_PASSWORD" \
  UBUNTU_USB_ROOT_PASSWORD="$CHROOT_ROOT_PASSWORD" \
  /bin/bash -ceu '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  xargs -r apt-get install -y --no-install-recommends </tmp/linux-usb-packages.list
  locale-gen || true
  update-initramfs -u -k all || true
  useradd -m -s /bin/bash "${UBUNTU_USB_USER:-ubuntu}" || true
  echo "${UBUNTU_USB_USER:-ubuntu}:${UBUNTU_USB_PASSWORD:-ubuntu}" | chpasswd
  echo "root:${UBUNTU_USB_ROOT_PASSWORD:-${UBUNTU_USB_PASSWORD:-ubuntu}}" | chpasswd
  usermod -aG sudo "${UBUNTU_USB_USER:-ubuntu}" || true
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=UbuntuUSB --removable --recheck
  update-grub
'
cleanup
trap - EXIT
if [ -n "$OUTPUT_PATH" ]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  mv "$IMAGE_PATH" "$OUTPUT_PATH"
else
  echo "Image ready: $IMAGE_PATH"
fi
