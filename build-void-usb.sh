#!/usr/bin/env bash
# Build a configurable, preinstalled Void Linux USB image with xbps-install -r.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-ledit-void.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
VOID_REPOSITORY="${VOID_REPOSITORY:-current}"
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
if [ "$(uname -s)" = "Darwin" ] && [ "${VOID_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  mkdir -p "$SCRIPT_DIR/.work"
  chmod 700 "$SCRIPT_DIR/.work" 2>/dev/null || true
  docker_env_file="$SCRIPT_DIR/.work/void-docker-env-$$"
  {
    printf '%s\n' \
      "VOID_USB_BUILD_IN_DOCKER=1" \
      "IMAGE_NAME=$IMAGE_NAME" \
      "IMAGE_SIZE=$IMAGE_SIZE" \
      "VOID_REPOSITORY=$VOID_REPOSITORY" \
      "ARCH=$ARCH" \
      "WORK_DIR=/tmp/void-work" \
      "VOID_LOCALREPO=/work/.work/void-localrepo-cache"
    if [ -n "$OUTPUT_PATH" ]; then
      mkdir -p "$(dirname "$OUTPUT_PATH")"
      output_dir="$(cd "$(dirname "$OUTPUT_PATH")" && pwd -P)"
      output_base="$(basename "$OUTPUT_PATH")"
      printf '%s\n' "OUTPUT_PATH=/out/$output_base"
    fi
    for name in LEDIT_USB_USER LEDIT_USB_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_HOSTNAME LEDIT_USB_TIMEZONE LEDIT_USB_LOCALE LEDIT_USB_LANGUAGE LEDIT_USB_CONSOLE_KEYMAP LEDIT_USB_XKB_LAYOUT LEDIT_USB_XKB_VARIANT LEDIT_USB_XKB_MODEL LEDIT_USB_DESKTOP LEDIT_USB_TILING_WMS LEDIT_USB_DEFAULT_SESSION LEDIT_USB_DISPLAY_MANAGER LEDIT_USB_NETWORK LEDIT_USB_WIFI LEDIT_USB_BLUETOOTH LEDIT_USB_AUDIO LEDIT_USB_BROWSER LEDIT_USB_FIRMWARE LEDIT_USB_LEGACY_X11_DRIVERS LEDIT_USB_BOOTLOADER LEDIT_USB_KERNEL_FLAVOR LEDIT_USB_BOOT_TIMEOUT LEDIT_USB_SYSTEMD_BOOT_CONSOLE_MODE LEDIT_USB_AUTO_RESIZE LEDIT_USB_EXTRA_PACKAGES LEDIT_USB_PROFILE; do
      value="${!name-}"
      case "$name" in
        LEDIT_USB_PASSWORD_FILE|LEDIT_USB_ROOT_PASSWORD_FILE)
          if [ -n "$value" ] && [ -f "$value" ]; then
            direct_name="${name%_FILE}"
            printf '%s=%s\n' "$direct_name" "$(cat "$value")"
            printf '%s=\n' "$name"
            continue
          fi
          ;;
      esac
      if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then value="/work/${value#"$SCRIPT_DIR"/}"; fi
      printf '%s=%s\n' "$name" "$value"
    done
  } > "$docker_env_file"
  chmod 600 "$docker_env_file" 2>/dev/null || true
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  if [ -n "$OUTPUT_PATH" ]; then docker_mounts+=(-v "$output_dir:/out"); fi
  docker_name_args=()
  if [ -n "${VOID_USB_DOCKER_NAME:-}" ]; then
    if [[ "$VOID_USB_DOCKER_NAME" == *[!A-Za-z0-9_.-]* ]]; then echo "Invalid Docker container name: $VOID_USB_DOCKER_NAME" >&2; exit 1; fi
    docker_name_args=(--name "$VOID_USB_DOCKER_NAME")
  fi
  if docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged --env-file "$docker_env_file" "${docker_mounts[@]}" -w /work ghcr.io/void-linux/void-glibc-full:latest sh -ceu '
    # The Void xbps-install HTTP fetcher (libfetch) issues range requests that some
    # CDNs reject with HTTP 416 under x86 emulation on Apple Silicon (Rosetta),
    # which breaks repo sync. xbps-fetch uses a different code path that works, so
    # we build a local file mirror: fetch repodata with xbps-fetch, resolve the
    # dependency closure with xbps-install -n, fetch every needed .xbps with
    # xbps-fetch, then install purely from the local repo (no network fetch).
    set -e
    REPO=https://repo-default.voidlinux.org/current
    LR=/tmp/void-localrepo
    rm -rf "$LR"; mkdir -p "$LR"
    xbps-fetch -o "$LR/x86_64-repodata" "$REPO/x86_64-repodata" 2>&1 | tail -1
    TOOLS="xbps bash parted dosfstools e2fsprogs grub grub-x86_64-efi efibootmgr kpartx"
    echo "[void-build] Resolving build-tool dependencies via local mirror"
    for p in $(xbps-install -n -R "$LR" $TOOLS 2>/dev/null | awk "{print \$1}"); do
      fn="$p.x86_64.xbps"
      [ -f "$LR/$fn" ] || xbps-fetch -o "$LR/$fn" "$REPO/$fn" 2>&1 | tail -1
    done
    echo "[void-build] Installing build tools from local mirror"
    xbps-install -y -R "$LR" $TOOLS 2>&1 | tail -3
    chmod +x build-void-usb.sh configure-void-usb.sh
    exec ./build-void-usb.sh
  '; then
    rm -f "$docker_env_file"
    exit 0
  fi
  rm -f "$docker_env_file"
  echo "[void-build] Custom Void installroot build failed; no live-ISO fallback is used." >&2
  exit 1
fi
for tool in xbps-install xbps-reconfigure parted mkfs.vfat mkfs.ext4 mount umount blkid truncate; do need "$tool"; done
if [ "$(uname -s)" = "Darwin" ]; then echo "Void image builds require native Linux for loop mounts; use a Linux VM/container." >&2; exit 1; fi
if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "Void image build must run as root (xbps-install -r + loop mounts)." >&2; exit 1; fi
if [ "${VOID_USB_BUILD_IN_DOCKER:-0}" = "1" ]; then
  [ -e /dev/loop-control ] || mknod /dev/loop-control c 10 237 || true
  for i in $(seq 0 15); do [ -e "/dev/loop$i" ] || mknod "/dev/loop$i" b 7 "$i" || true; done
fi

# Install Void packages into a target root using a local file:// mirror.
# xbps-install's internal HTTP fetcher (libfetch) issues range requests that some
# CDNs reject with HTTP 416 under x86 emulation on Apple Silicon (Rosetta).
# xbps-fetch uses a different code path that works, so we fetch repodata + every
# resolved .xbps with xbps-fetch into a local dir, then install from there.
# Args: <repo_url> <arch> <localrepo_dir> <root_dir> <pkg...>
void_local_install() {
  repo_url="$1"; varch="$2"; localrepo="$3"; root_dir="$4"; shift 4
  mkdir -p "$localrepo"
  repodata="$localrepo/${varch}-repodata"
  [ -s "$repodata" ] || xbps-fetch -o "$repodata" "$repo_url/${varch}-repodata" 2>&1 | tail -1
  echo "[void-build] Resolving package closure: $*"
  pkgs=$(XBPS_ARCH="$varch" xbps-install -n -R "$localrepo" -r "$root_dir" "$@" 2>/dev/null | awk '{print $1}')
  for p in $pkgs; do
    fn="$p.${varch}.xbps"
    [ -f "$localrepo/$fn" ] || xbps-fetch -o "$localrepo/$fn" "$repo_url/$fn" 2>&1 | tail -1
  done
  echo "[void-build] Installing $(echo "$pkgs" | wc -w) packages into $root_dir from local mirror"
  XBPS_ARCH="$varch" xbps-install -y -R "$localrepo" -r "$root_dir" "$@" 2>&1 | tail -3
}

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR" 2>/dev/null || true
rm -rf "$ROOT_DIR" "$MOUNT_DIR"
mkdir -p "$ROOT_DIR" "$MOUNT_DIR"
rm -f "$IMAGE_PATH"
truncate -s "$IMAGE_SIZE" "$IMAGE_PATH"
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

VOID_LOCALREPO="${VOID_LOCALREPO:-$WORK_DIR/void-localrepo}"
void_local_install "$REPO_URL" "$ARCH" "$VOID_LOCALREPO" "$MOUNT_DIR" base-system xbps grub-x86_64-efi efibootmgr bash
for fs in dev proc sys run; do mount --rbind "/$fs" "$MOUNT_DIR/$fs"; done
cleanup_chroot_binds() { set +e; for fs in run sys proc dev; do mountpoint -q "$MOUNT_DIR/$fs" && umount -R "$MOUNT_DIR/$fs"; done; }
trap 'cleanup_chroot_binds; cleanup' EXIT
cp "$SCRIPT_DIR/configure-void-usb.sh" "$MOUNT_DIR/root/configure-void-usb.sh"
chmod +x "$MOUNT_DIR/root/configure-void-usb.sh"
CONFIG_PACKAGES="$(LEDIT_USB_DRY_RUN=1 chroot "$MOUNT_DIR" /root/configure-void-usb.sh | awk '/^ packages:/ {sub(/^ packages:[[:space:]]*/, ""); print; exit}')"
if [ -n "$CONFIG_PACKAGES" ]; then
  # shellcheck disable=SC2086
  void_local_install "$REPO_URL" "$ARCH" "$VOID_LOCALREPO" "$MOUNT_DIR" $CONFIG_PACKAGES
fi
LEDIT_USB_SKIP_PACKAGE_INSTALL=1 chroot "$MOUNT_DIR" /root/configure-void-usb.sh
xbps-reconfigure -r "$MOUNT_DIR" -fa
ROOT_UUID="$(blkid -s UUID -o value "$ROOT_PART")"
mkdir -p "$MOUNT_DIR/boot/grub"
cat > "$MOUNT_DIR/boot/grub/grub.cfg" <<EOF
set default=0
set timeout=${LEDIT_USB_BOOT_TIMEOUT:-3}
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
