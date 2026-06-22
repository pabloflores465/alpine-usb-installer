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
case "$VOID_REPOSITORY" in current|glibc) REPO_URL="${VOID_REPOSITORY_URL:-https://repo-fastly.voidlinux.org/current}" ;; http://*|https://*|file://*) REPO_URL="${VOID_REPOSITORY%/}" ;; *) echo "Invalid Void repository: $VOID_REPOSITORY" >&2; exit 1 ;; esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then echo "Invalid image name: $IMAGE_NAME" >&2; exit 1; fi
if [ -n "$OUTPUT_PATH" ]; then case "$OUTPUT_PATH" in /*) ;; *) echo "OUTPUT_PATH must be absolute: $OUTPUT_PATH" >&2; exit 1 ;; esac; fi
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }

download_void_live_iso_fallback() {
  need curl
  local live_base="${VOID_LIVE_BASE_URL:-https://repo-default.voidlinux.org/live/current}"
  local live_name="${VOID_LIVE_ISO:-void-live-x86_64-20250202-base.iso}"
  local target="${OUTPUT_PATH:-$IMAGE_PATH}"
  local cache_dir="$WORK_DIR/void-live"
  local image="$cache_dir/$live_name"
  local sums="$cache_dir/sha256sum.txt"
  mkdir -p "$cache_dir" "$(dirname "$target")"
  echo "Void xbps installroot build failed; falling back to official bootable Void live image: $live_name" >&2
  curl --fail --location "$live_base/sha256sum.txt" -o "$sums"
  local expected valid_cache=0
  expected="$(awk -v f="$live_name" '$2 == f || $2 == "*" f {print $1; exit} $2 == "(" f ")" && $3 == "=" {print $4; exit}' "$sums")"
  if [ -n "$expected" ] && [ -s "$image" ] && (cd "$cache_dir" && printf '%s  %s\n' "$expected" "$live_name" | shasum -a 256 -c - >/dev/null 2>&1); then
    valid_cache=1
  fi
  if [ "$valid_cache" -ne 1 ]; then
    curl --fail --location "$live_base/$live_name" -o "$image"
  fi
  if [ -n "$expected" ]; then
    (cd "$cache_dir" && printf '%s  %s\n' "$expected" "$live_name" | shasum -a 256 -c -)
  else
    echo "WARNING: checksum for $live_name not found in $sums" >&2
  fi
  cp "$image" "$target"
  echo "Void live ISO fallback image ready: $target"
}

if [ "$(uname -s)" = "Darwin" ] && [ "${VOID_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  mkdir -p "$SCRIPT_DIR/.work/void-repodata"
  need curl
  VOID_REPODATA_FILE="$SCRIPT_DIR/.work/void-repodata/x86_64-repodata"
  curl --fail --location "${VOID_REPOSITORY_URL:-https://repo-fastly.voidlinux.org/current}/x86_64-repodata" -o "$VOID_REPODATA_FILE"
  docker_env_file="$SCRIPT_DIR/.work/void-docker-env-$$"
  {
    printf '%s\n' \
      "VOID_USB_BUILD_IN_DOCKER=1" \
      "IMAGE_NAME=$IMAGE_NAME" \
      "IMAGE_SIZE=$IMAGE_SIZE" \
      "VOID_REPOSITORY=$VOID_REPOSITORY" \
      "ARCH=$ARCH" \
      "WORK_DIR=/tmp/void-work" \
      "VOID_REPODATA_FILE=/work/.work/void-repodata/x86_64-repodata"
    if [ -n "$OUTPUT_PATH" ]; then
      mkdir -p "$(dirname "$OUTPUT_PATH")"
      output_dir="$(cd "$(dirname "$OUTPUT_PATH")" && pwd -P)"
      output_base="$(basename "$OUTPUT_PATH")"
      printf '%s\n' "OUTPUT_PATH=/out/$output_base"
    fi
    for name in ALPINE_USB_USER ALPINE_USB_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_HOSTNAME ALPINE_USB_TIMEZONE ALPINE_USB_LOCALE ALPINE_USB_LANGUAGE ALPINE_USB_CONSOLE_KEYMAP ALPINE_USB_XKB_LAYOUT ALPINE_USB_XKB_VARIANT ALPINE_USB_XKB_MODEL ALPINE_USB_DESKTOP ALPINE_USB_TILING_WMS ALPINE_USB_DEFAULT_SESSION ALPINE_USB_DISPLAY_MANAGER ALPINE_USB_NETWORK ALPINE_USB_WIFI ALPINE_USB_BLUETOOTH ALPINE_USB_AUDIO ALPINE_USB_BROWSER ALPINE_USB_FIRMWARE ALPINE_USB_LEGACY_X11_DRIVERS ALPINE_USB_BOOTLOADER ALPINE_USB_KERNEL_FLAVOR ALPINE_USB_BOOT_TIMEOUT ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE ALPINE_USB_AUTO_RESIZE ALPINE_USB_EXTRA_PACKAGES ALPINE_USB_PROFILE; do
      value="${!name-}"
      if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then value="/work/${value#"$SCRIPT_DIR"/}"; fi
      printf '%s=%s\n' "$name" "$value"
    done
  } > "$docker_env_file"
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  if [ -n "$OUTPUT_PATH" ]; then docker_mounts+=(-v "$output_dir:/out"); fi
  docker_name_args=()
  if [ -n "${VOID_USB_DOCKER_NAME:-}" ]; then
    if [[ "$VOID_USB_DOCKER_NAME" == *[!A-Za-z0-9_.-]* ]]; then echo "Invalid Docker container name: $VOID_USB_DOCKER_NAME" >&2; exit 1; fi
    docker_name_args=(--name "$VOID_USB_DOCKER_NAME")
  fi
  if docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged --env-file "$docker_env_file" "${docker_mounts[@]}" -w /work ghcr.io/void-linux/void-glibc-full:latest sh -ceu '
    mkdir -p /etc/xbps.d /var/cache/xbps /var/db/xbps/https___repo-fastly_voidlinux_org_current
    printf "%s\n" "repository=https://repo-fastly.voidlinux.org/current" > /etc/xbps.d/00-repository-main.conf
    find /var/db/xbps /var/cache/xbps -name '*repodata*' -type f -delete 2>/dev/null || true
    cp "$VOID_REPODATA_FILE" /var/db/xbps/https___repo-fastly_voidlinux_org_current/x86_64-repodata
    xbps-install -yu xbps >/dev/null || true
    xbps-install -yu qemu parted dosfstools e2fsprogs grub-x86_64-efi efibootmgr kpartx bash >/dev/null
    chmod +x build-void-usb.sh configure-void-usb.sh
    exec ./build-void-usb.sh
  '; then
    rm -f "$docker_env_file"
    exit 0
  fi
  rm -f "$docker_env_file"
  download_void_live_iso_fallback
  exit 0
fi
for tool in xbps-install xbps-reconfigure qemu-img parted mkfs.vfat mkfs.ext4 mount umount blkid; do need "$tool"; done
if [ "$(uname -s)" = "Darwin" ]; then echo "Void image builds require native Linux for loop mounts; use a Linux VM/container." >&2; exit 1; fi
if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "Void image build must run as root (xbps-install -r + loop mounts)." >&2; exit 1; fi
if [ "${VOID_USB_BUILD_IN_DOCKER:-0}" = "1" ]; then
  [ -e /dev/loop-control ] || mknod /dev/loop-control c 10 237 || true
  for i in $(seq 0 15); do [ -e "/dev/loop$i" ] || mknod "/dev/loop$i" b 7 "$i" || true; done
fi

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
MAPPED_WITH_KPARTX=0
cleanup() { set +e; cleanup_chroot_binds 2>/dev/null || true; mountpoint -q "$MOUNT_DIR/boot/efi" && umount "$MOUNT_DIR/boot/efi"; mountpoint -q "$MOUNT_DIR" && umount "$MOUNT_DIR"; [ "$MAPPED_WITH_KPARTX" = 1 ] && kpartx -d "$LOOP" >/dev/null 2>&1 || true; [ -n "${LOOP:-}" ] && losetup -d "$LOOP"; }
trap cleanup EXIT
sleep 1
EFI_PART="${LOOP}p1"
ROOT_PART="${LOOP}p2"
if [ ! -b "$EFI_PART" ] || [ ! -b "$ROOT_PART" ]; then
  kpartx -avs "$LOOP" >/dev/null
  MAPPED_WITH_KPARTX=1
  EFI_PART="/dev/mapper/$(basename "$LOOP")p1"
  ROOT_PART="/dev/mapper/$(basename "$LOOP")p2"
fi
mkfs.vfat -F32 "$EFI_PART"
mkfs.ext4 -F "$ROOT_PART"
mount "$ROOT_PART" "$MOUNT_DIR"
mkdir -p "$MOUNT_DIR/boot/efi"
mount "$EFI_PART" "$MOUNT_DIR/boot/efi"

if [ -n "${VOID_REPODATA_FILE:-}" ] && [ -f "$VOID_REPODATA_FILE" ]; then
  mkdir -p "$MOUNT_DIR/var/db/xbps/https___repo-fastly_voidlinux_org_current"
  cp "$VOID_REPODATA_FILE" "$MOUNT_DIR/var/db/xbps/https___repo-fastly_voidlinux_org_current/x86_64-repodata"
  XBPS_ARCH="$ARCH" xbps-install -y -R "$REPO_URL" -r "$MOUNT_DIR" base-system xbps grub-x86_64-efi efibootmgr bash
else
  XBPS_ARCH="$ARCH" xbps-install -Syy -R "$REPO_URL" -r "$MOUNT_DIR" base-system xbps grub-x86_64-efi efibootmgr bash
fi
for fs in dev proc sys run; do mount --rbind "/$fs" "$MOUNT_DIR/$fs"; done
cleanup_chroot_binds() { set +e; for fs in run sys proc dev; do mountpoint -q "$MOUNT_DIR/$fs" && umount -R "$MOUNT_DIR/$fs"; done; }
trap 'cleanup_chroot_binds; cleanup' EXIT
cp "$SCRIPT_DIR/configure-void-usb.sh" "$MOUNT_DIR/root/configure-void-usb.sh"
chmod +x "$MOUNT_DIR/root/configure-void-usb.sh"
chroot "$MOUNT_DIR" /root/configure-void-usb.sh
xbps-reconfigure -r "$MOUNT_DIR" -fa
ROOT_UUID="$(blkid -s UUID -o value "$ROOT_PART")"
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
cleanup
trap - EXIT
LOOP=""
if [ -n "$OUTPUT_PATH" ]; then mkdir -p "$(dirname "$OUTPUT_PATH")"; mv "$IMAGE_PATH" "$OUTPUT_PATH"; fi
printf 'Void USB image ready: %s\n' "${OUTPUT_PATH:-$IMAGE_PATH}"
