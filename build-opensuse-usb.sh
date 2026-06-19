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
if [ "$(uname -s)" = Darwin ] && [ "${OPENSUSE_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  docker_env=(-e OPENSUSE_USB_BUILD_IN_DOCKER=1 -e IMAGE_NAME="$IMAGE_NAME" -e IMAGE_SIZE="$IMAGE_SIZE" -e WORK_DIR=/tmp/opensuse-work)
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  if [ -n "$OUTPUT_PATH" ]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    output_dir="$(cd "$(dirname "$OUTPUT_PATH")" && pwd -P)"
    output_base="$(basename "$OUTPUT_PATH")"
    docker_mounts+=(-v "$output_dir:/out")
    docker_env+=(-e "OUTPUT_PATH=/out/$output_base")
  fi
  for name in OPENSUSE_RELEASE OPENSUSE_USB_PROFILE OPENSUSE_USB_USER OPENSUSE_USB_PASSWORD_FILE OPENSUSE_USB_ROOT_PASSWORD_FILE OPENSUSE_USB_HOSTNAME OPENSUSE_USB_TIMEZONE OPENSUSE_USB_LOCALE OPENSUSE_USB_LANGUAGE OPENSUSE_USB_CONSOLE_KEYMAP OPENSUSE_USB_XKB_LAYOUT OPENSUSE_USB_XKB_VARIANT OPENSUSE_USB_XKB_MODEL OPENSUSE_USB_DESKTOP OPENSUSE_USB_TILING_WMS OPENSUSE_USB_DEFAULT_SESSION OPENSUSE_USB_DISPLAY_MANAGER OPENSUSE_USB_NETWORK OPENSUSE_USB_WIFI OPENSUSE_USB_BLUETOOTH OPENSUSE_USB_AUDIO OPENSUSE_USB_BROWSER OPENSUSE_USB_FIRMWARE OPENSUSE_USB_LEGACY_X11_DRIVERS OPENSUSE_USB_BOOTLOADER OPENSUSE_USB_KERNEL_FLAVOR OPENSUSE_USB_BOOT_TIMEOUT OPENSUSE_USB_SYSTEMD_BOOT_CONSOLE_MODE OPENSUSE_USB_AUTO_RESIZE OPENSUSE_USB_EXTRA_PACKAGES; do
    value="${!name-}"
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then value="/work/${value#"$SCRIPT_DIR"/}"; fi
    docker_env+=(-e "$name=$value")
  done
  exec docker run --rm --platform linux/amd64 --privileged "${docker_env[@]}" "${docker_mounts[@]}" -w /work opensuse/tumbleweed bash -ceu '
    zypper --non-interactive refresh >/dev/null
    zypper --non-interactive install -y bash python3 qemu-tools parted e2fsprogs grub2 grub2-x86_64-efi >/dev/null
    chmod +x build-opensuse-usb.sh configure-opensuse-usb.sh
    exec ./build-opensuse-usb.sh
  '
fi
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
