#!/usr/bin/env bash
# Build a configurable, installed Gentoo Linux USB image.
set -euo pipefail

log() {
  printf '[gentoo-build] %s\n' "$*"
}

fail() {
  printf '[gentoo-build] ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Required tool not found: $1"
}

lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_enabled() {
  case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac
}

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

sha512_file() {
  if command -v sha512sum >/dev/null 2>&1; then
    sha512sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 512 "$1" | awk '{print $1}'
  else
    fail "Required tool not found: sha512sum or shasum"
  fi
}

read_secret() {
  local file_var="$1" value_var="$2" default_value="$3" file_value direct_value
  file_value="${!file_var-}"
  direct_value="${!value_var-}"
  if [ -n "$file_value" ]; then
    [ -f "$file_value" ] || fail "Secret file not found: $file_value"
    cat "$file_value"
  elif [ -n "$direct_value" ]; then
    printf '%s' "$direct_value"
  else
    printf '%s' "$default_value"
  fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-gentoo-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
ARCH_VALUE="${ARCH:-x86_64}"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
STAGE3_CACHE_DIR="${GENTOO_STAGE3_CACHE_DIR:-$WORK_DIR/gentoo-stage3}"
PORTAGE_REPO_CACHE_DIR="${GENTOO_PORTAGE_REPO_CACHE_DIR:-$WORK_DIR/gentoo-portage-repo/gentoo}"
BUILD_DIR="${GENTOO_BUILD_DIR:-/var/tmp/gentoo-usb-build-$$}"
ALPINE_BASE_IMAGE="alpine:3.22@sha256:310c62b5e7ca5b08167e4384c68db0fd2905dd9c7493756d356e893909057601"
DOCKER_IMAGE="${GENTOO_USB_DOCKER_IMAGE:-$ALPINE_BASE_IMAGE}"
BUILDER_IMAGE="${GENTOO_USB_BUILDER_IMAGE:-gentoo-usb-builder:3.22-amd64}"
BUILDER_DOCKERFILE="${GENTOO_USB_BUILDER_DOCKERFILE:-$SCRIPT_DIR/scripts/Dockerfile.gentoo-builder}"
BOOTLOADER="$(lower "${ALPINE_USB_BOOTLOADER:-${BOOTLOADER:-grub}}")"
[ "$BOOTLOADER" = "systemdboot" ] && BOOTLOADER="systemd-boot"

case "$ARCH_VALUE" in
  x86_64|amd64) GENTOO_ARCH=amd64 ;;
  *) fail "Gentoo installed image builder currently supports x86_64/amd64 only (got: $ARCH_VALUE)" ;;
esac
case "$BOOTLOADER" in
  grub) ;;
  systemd-boot) fail "Gentoo installed image builder currently supports GRUB only; choose --bootloader grub" ;;
  *) fail "Unsupported bootloader: $BOOTLOADER" ;;
esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  fail "Invalid image name: $IMAGE_NAME"
fi
if [ -n "$OUTPUT_PATH" ]; then
  case "$OUTPUT_PATH" in
    /*) ;;
    *) fail "OUTPUT_PATH must be absolute: $OUTPUT_PATH" ;;
  esac
fi

# macOS cannot chroot/mount Linux rootfs natively. Run the full Gentoo builder in
# the same privileged Docker style used by the Alpine backend. Native Linux can
# also opt into this path with GENTOO_USB_FORCE_DOCKER=1.
if { [ "$(uname -s)" = "Darwin" ] || is_enabled "${GENTOO_USB_FORCE_DOCKER:-0}"; } && [ "${GENTOO_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    fail "Docker not found. Install Docker Desktop and try again."
  fi
  if ! docker info >/dev/null 2>&1; then
    fail "Docker is not running. Start Docker Desktop and try again."
  fi

  pass_env=(
    IMAGE_NAME OUTPUT_PATH IMAGE_SIZE ARCH
    ALPINE_USB_USER ALPINE_USB_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_HOSTNAME
    ALPINE_USB_TIMEZONE ALPINE_USB_LOCALE ALPINE_USB_LANGUAGE
    ALPINE_USB_CONSOLE_KEYMAP ALPINE_USB_XKB_LAYOUT ALPINE_USB_XKB_VARIANT ALPINE_USB_XKB_MODEL
    ALPINE_USB_DESKTOP ALPINE_USB_TILING_WMS ALPINE_USB_DEFAULT_SESSION ALPINE_USB_DISPLAY_MANAGER
    ALPINE_USB_NETWORK ALPINE_USB_WIFI ALPINE_USB_BLUETOOTH ALPINE_USB_AUDIO ALPINE_USB_BROWSER
    ALPINE_USB_FIRMWARE ALPINE_USB_LEGACY_X11_DRIVERS ALPINE_USB_BOOTLOADER ALPINE_USB_KERNEL_FLAVOR
    ALPINE_USB_BOOT_TIMEOUT ALPINE_USB_AUTO_RESIZE ALPINE_USB_EXTRA_PACKAGES ALPINE_USB_PROFILE
    GENTOO_STAGE3_BRANCH GENTOO_STAGE3_BASE_URL GENTOO_STAGE3_CACHE_DIR GENTOO_PORTAGE_REPO_CACHE_DIR
    GENTOO_BUILD_DIR GENTOO_USE_BINPKGS GENTOO_EMERGE_SYNC GENTOO_EMERGE_OPTS GENTOO_MAKEOPTS
    GENTOO_BUILD_JOBS GENTOO_ACCEPT_LICENSE GENTOO_USE_FLAGS GENTOO_FEATURES GENTOO_CLEAN_BUILD_CACHE
  )
  docker_env=(-e GENTOO_USB_BUILD_IN_DOCKER=1)
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  docker_name_args=()
  if [ -n "${GENTOO_USB_DOCKER_NAME:-}" ]; then
    docker_name_args=(--name "$GENTOO_USB_DOCKER_NAME")
  fi
  for name in "${pass_env[@]}"; do
    value="${!name-}"
    if [ "$name" = "OUTPUT_PATH" ] && [ -n "$value" ]; then
      mkdir -p "$(dirname "$value")"
      output_dir="$(cd "$(dirname "$value")" && pwd -P)"
      output_base="$(basename "$value")"
      docker_mounts+=(-v "$output_dir:/out")
      docker_env+=(-e "OUTPUT_PATH=/out/$output_base")
      continue
    fi
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then
      value="/work/${value#"$SCRIPT_DIR"/}"
    fi
    if { [ "$name" = "GENTOO_STAGE3_CACHE_DIR" ] || [ "$name" = "GENTOO_PORTAGE_REPO_CACHE_DIR" ]; } && [ -n "$value" ] && [[ "$value" == "$SCRIPT_DIR/"* ]]; then
      value="/work/${value#"$SCRIPT_DIR"/}"
    fi
    docker_env+=(-e "$name=$value")
  done

  if [ "${GENTOO_USB_SKIP_BUILDER_CACHE:-0}" != "1" ] && [ -f "$BUILDER_DOCKERFILE" ]; then
    if [ "${GENTOO_USB_REBUILD_BUILDER:-0}" = "1" ] || ! docker image inspect "$BUILDER_IMAGE" >/dev/null 2>&1; then
      log "Building cached Gentoo USB builder image ($BUILDER_IMAGE)"
      docker build --platform linux/amd64 -f "$BUILDER_DOCKERFILE" -t "$BUILDER_IMAGE" "$(dirname "$BUILDER_DOCKERFILE")"
    fi
    log "Starting Docker build container with cached Gentoo USB build tools ($BUILDER_IMAGE)"
    exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
      "${docker_env[@]}" \
      "${docker_mounts[@]}" \
      -w /work \
      "$BUILDER_IMAGE" \
      bash -ceu 'chmod +x build-gentoo-usb.sh configure-gentoo-usb.sh; exec ./build-gentoo-usb.sh'
  fi

  log "Starting fresh Docker build container with Gentoo USB build tools ($DOCKER_IMAGE)"
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
    "${docker_env[@]}" \
    "${docker_mounts[@]}" \
    -w /work \
    "$DOCKER_IMAGE" \
    sh -ceu '
      apk add --no-cache bash curl ca-certificates coreutils util-linux parted dosfstools \
        e2fsprogs mtools grub grub-efi xz tar zstd rsync findutils grep gawk sed shadow \
        gzip bzip2 kmod >/dev/null
      chmod +x build-gentoo-usb.sh configure-gentoo-usb.sh
      exec ./build-gentoo-usb.sh
    '
fi

need awk
need curl
need tar
need parted
need truncate
need mkfs.vfat
need mkfs.ext4
need mmd
need mcopy
need grub-mkstandalone
need uuidgen
need dd
need chroot
need mount
need rsync

if [ "$(id -u)" != "0" ]; then
  fail "Gentoo installed image build needs root for chroot mounts. On macOS this happens through Docker; on Linux run as root or set GENTOO_USB_FORCE_DOCKER=1."
fi

OUTPUT=${OUTPUT_PATH:-$SCRIPT_DIR/$IMAGE_NAME}
mkdir -p "$WORK_DIR" "$STAGE3_CACHE_DIR" "$(dirname "$PORTAGE_REPO_CACHE_DIR")" "$(dirname "$OUTPUT")"
chmod 700 "$WORK_DIR" 2>/dev/null || true

log "Validating Gentoo package plan"
ALPINE_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-gentoo-usb.sh"

BASE_URL="${GENTOO_STAGE3_BASE_URL:-https://distfiles.gentoo.org/releases/$GENTOO_ARCH/autobuilds/current-stage3-$GENTOO_ARCH-openrc}"
LATEST_TXT="$STAGE3_CACHE_DIR/latest-stage3-$GENTOO_ARCH-openrc.txt"
mkdir -p "$STAGE3_CACHE_DIR"

log "Fetching Gentoo latest stage3 metadata"
curl -fsSL --retry 3 "$BASE_URL/latest-stage3-$GENTOO_ARCH-openrc.txt" -o "$LATEST_TXT"
STAGE3_NAME=$(awk '/stage3-.*\.tar\.(xz|zst)[[:space:]]+[0-9]+/ && $1 !~ /^#/ {print $1; exit}' "$LATEST_TXT")
[ -n "$STAGE3_NAME" ] || fail "Could not parse latest Gentoo stage3 name from $LATEST_TXT"
case "$STAGE3_NAME" in
  */*) STAGE3_PATH_PART=$STAGE3_NAME; STAGE3_FILE=${STAGE3_NAME##*/} ;;
  *) STAGE3_PATH_PART=$STAGE3_NAME; STAGE3_FILE=$STAGE3_NAME ;;
esac

STAGE3_URL="$BASE_URL/$STAGE3_PATH_PART"
DIGEST_URL="$STAGE3_URL.DIGESTS"
STAGE3_PATH="$STAGE3_CACHE_DIR/$STAGE3_FILE"
DIGEST_PATH="$STAGE3_CACHE_DIR/$STAGE3_FILE.DIGESTS"

if [ ! -s "$STAGE3_PATH" ]; then
  log "Downloading $STAGE3_URL"
  curl -fsSL --retry 3 -C - "$STAGE3_URL" -o "$STAGE3_PATH"
else
  log "Reusing cached stage3 $STAGE3_PATH"
fi

log "Fetching and verifying SHA512 digest"
curl -fsSL --retry 3 "$DIGEST_URL" -o "$DIGEST_PATH"
EXPECTED=$(awk -v name="$STAGE3_FILE" 'length($1) == 128 && $2 == name {print $1; exit}' "$DIGEST_PATH")
[ -n "$EXPECTED" ] || fail "Could not find SHA512 digest for $STAGE3_FILE in $DIGEST_PATH"
ACTUAL=$(sha512_file "$STAGE3_PATH")
if [ "$ACTUAL" != "$EXPECTED" ]; then
  rm -f "$STAGE3_PATH"
  fail "SHA512 mismatch for $STAGE3_FILE"
fi

ROOTFS="$BUILD_DIR/rootfs"
ESP_IMG="$BUILD_DIR/esp.img"
ROOT_IMG="$BUILD_DIR/root.img"
GRUB_CFG="$BUILD_DIR/grub.cfg"
STANDALONE_CFG="$BUILD_DIR/grub-standalone.cfg"
BOOT_EFI="$BUILD_DIR/BOOTX64.EFI"
TMP_OUTPUT="$OUTPUT.tmp"
CHROOT_MOUNTED=0

cleanup_chroot_mounts() {
  if [ "$CHROOT_MOUNTED" = "1" ]; then
    umount -R "$ROOTFS/run" >/dev/null 2>&1 || true
    umount -R "$ROOTFS/dev" >/dev/null 2>&1 || true
    umount -R "$ROOTFS/sys" >/dev/null 2>&1 || true
    umount -R "$ROOTFS/proc" >/dev/null 2>&1 || true
    CHROOT_MOUNTED=0
  fi
}

save_portage_cache() {
  if [ -d "$ROOTFS/var/db/repos/gentoo/profiles" ]; then
    log "Saving Gentoo repository metadata cache"
    mkdir -p "$PORTAGE_REPO_CACHE_DIR"
    rsync -a --delete "$ROOTFS/var/db/repos/gentoo/" "$PORTAGE_REPO_CACHE_DIR/" || true
  fi
}

cleanup() {
  cleanup_chroot_mounts
  if [ "${GENTOO_KEEP_BUILD_DIR:-0}" != "1" ]; then
    rm -rf "$BUILD_DIR"
  else
    log "Keeping build directory: $BUILD_DIR"
  fi
}
trap cleanup EXIT INT TERM

rm -rf "$BUILD_DIR"
mkdir -p "$ROOTFS"
log "Extracting Gentoo stage3 into build root"
tar -xpf "$STAGE3_PATH" -C "$ROOTFS" --xattrs-include='*.*' --numeric-owner

if [ -d "$PORTAGE_REPO_CACHE_DIR/profiles" ]; then
  log "Restoring cached Gentoo repository metadata"
  mkdir -p "$ROOTFS/var/db/repos/gentoo"
  rsync -a --delete "$PORTAGE_REPO_CACHE_DIR/" "$ROOTFS/var/db/repos/gentoo/"
  if [ -z "${GENTOO_EMERGE_SYNC:-}" ]; then
    GENTOO_EMERGE_SYNC=0
  fi
fi

cp /etc/resolv.conf "$ROOTFS/etc/resolv.conf" 2>/dev/null || true
cp "$SCRIPT_DIR/configure-gentoo-usb.sh" "$ROOTFS/root/configure-gentoo-usb.sh"
chmod 700 "$ROOTFS/root/configure-gentoo-usb.sh"

USER_PASSWORD="$(read_secret ALPINE_USB_PASSWORD_FILE ALPINE_USB_PASSWORD gentoo)"
ROOT_PASSWORD="$(read_secret ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD "$USER_PASSWORD")"
ENV_FILE="$ROOTFS/root/gentoo-build.env"
{
  for name in \
    IMAGE_SIZE ARCH ALPINE_USB_USER ALPINE_USB_HOSTNAME ALPINE_USB_TIMEZONE ALPINE_USB_LOCALE \
    ALPINE_USB_LANGUAGE ALPINE_USB_CONSOLE_KEYMAP ALPINE_USB_XKB_LAYOUT ALPINE_USB_XKB_VARIANT \
    ALPINE_USB_XKB_MODEL ALPINE_USB_DESKTOP ALPINE_USB_TILING_WMS ALPINE_USB_DEFAULT_SESSION \
    ALPINE_USB_DISPLAY_MANAGER ALPINE_USB_NETWORK ALPINE_USB_WIFI ALPINE_USB_BLUETOOTH \
    ALPINE_USB_AUDIO ALPINE_USB_BROWSER ALPINE_USB_FIRMWARE ALPINE_USB_LEGACY_X11_DRIVERS \
    ALPINE_USB_BOOTLOADER ALPINE_USB_KERNEL_FLAVOR ALPINE_USB_BOOT_TIMEOUT ALPINE_USB_AUTO_RESIZE \
    ALPINE_USB_EXTRA_PACKAGES ALPINE_USB_PROFILE GENTOO_STAGE3_BRANCH GENTOO_USE_BINPKGS \
    GENTOO_EMERGE_SYNC GENTOO_EMERGE_OPTS GENTOO_MAKEOPTS GENTOO_BUILD_JOBS \
    GENTOO_ACCEPT_LICENSE GENTOO_USE_FLAGS GENTOO_FEATURES GENTOO_CLEAN_BUILD_CACHE; do
    printf 'export %s=%s\n' "$name" "$(shell_quote "${!name-}")"
  done
  printf 'export ALPINE_USB_PASSWORD=%s\n' "$(shell_quote "$USER_PASSWORD")"
  printf 'export ALPINE_USB_ROOT_PASSWORD=%s\n' "$(shell_quote "$ROOT_PASSWORD")"
  printf 'export ALPINE_USB_DRY_RUN=0\n'
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

mkdir -p "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" "$ROOTFS/run"
log "Mounting chroot API filesystems"
mount -t proc proc "$ROOTFS/proc"
mount --rbind /sys "$ROOTFS/sys"
mount --make-rslave "$ROOTFS/sys" >/dev/null 2>&1 || true
mount --rbind /dev "$ROOTFS/dev"
mount --make-rslave "$ROOTFS/dev" >/dev/null 2>&1 || true
mount --rbind /run "$ROOTFS/run"
mount --make-rslave "$ROOTFS/run" >/dev/null 2>&1 || true
CHROOT_MOUNTED=1

log "Configuring Gentoo rootfs and installing selected packages"
if ! chroot "$ROOTFS" /bin/bash -lc '. /root/gentoo-build.env; unset ALPINE_USB_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD_FILE; exec /root/configure-gentoo-usb.sh'; then
  save_portage_cache
  exit 1
fi
save_portage_cache
rm -f "$ENV_FILE" "$ROOTFS/root/configure-gentoo-usb.sh"
cleanup_chroot_mounts

ROOT_UUID="$(uuidgen)"
ESP_ID="$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n' | tr '[:lower:]' '[:upper:]')"
ESP_UUID="${ESP_ID:0:4}-${ESP_ID:4:4}"
mkdir -p "$ROOTFS/boot/efi"
cat > "$ROOTFS/etc/fstab" <<EOF
UUID=$ROOT_UUID  /          ext4  defaults,noatime  0 1
UUID=$ESP_UUID   /boot/efi  vfat  defaults,noatime  0 2
proc             /proc      proc  defaults          0 0
tmpfs            /tmp       tmpfs defaults,nosuid,nodev 0 0
EOF

KERNEL_PATH=$(find "$ROOTFS/boot" -maxdepth 1 -type f \( -name 'vmlinuz*' -o -name 'kernel-*' \) | sort | tail -n 1 || true)
[ -n "$KERNEL_PATH" ] || fail "No Gentoo kernel found in /boot after package installation"
KERNEL_REL="/${KERNEL_PATH#"$ROOTFS/"}"
INITRD_PATH=$(find "$ROOTFS/boot" -maxdepth 1 -type f \( -name 'initramfs*' -o -name 'initrd*' \) | sort | tail -n 1 || true)
INITRD_LINE=""
if [ -n "$INITRD_PATH" ]; then
  INITRD_REL="/${INITRD_PATH#"$ROOTFS/"}"
  INITRD_LINE="    initrd $INITRD_REL"
fi

cat > "$GRUB_CFG" <<EOF
set default=0
set timeout=${ALPINE_USB_BOOT_TIMEOUT:-3}
set timeout_style=menu

menuentry 'Gentoo Linux USB' {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux $KERNEL_REL root=UUID=$ROOT_UUID ro rootfstype=ext4 rootwait
$INITRD_LINE
}

menuentry 'Gentoo Linux USB (safe graphics)' {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux $KERNEL_REL root=UUID=$ROOT_UUID ro rootfstype=ext4 rootwait nomodeset
$INITRD_LINE
}
EOF

cat > "$STANDALONE_CFG" <<EOF
insmod part_gpt
insmod fat
insmod ext2
insmod search_fs_uuid
insmod configfile
search --no-floppy --file --set=esp /grub/grub.cfg
set prefix=(memdisk)/boot/grub
configfile (\$esp)/grub/grub.cfg

$(cat "$GRUB_CFG")
EOF

grub-mkstandalone \
  -O x86_64-efi \
  --modules="part_gpt fat ext2 gzio linux search_fs_uuid search_fs_file configfile normal" \
  -o "$BOOT_EFI" \
  "boot/grub/grub.cfg=$STANDALONE_CFG"

log "Creating raw GPT image $OUTPUT"
rm -f "$TMP_OUTPUT" "$ESP_IMG" "$ROOT_IMG"
truncate -s "$IMAGE_SIZE" "$TMP_OUTPUT"
parted -s "$TMP_OUTPUT" mklabel gpt
parted -s "$TMP_OUTPUT" unit MiB mkpart ESP fat32 1 513
parted -s "$TMP_OUTPUT" set 1 esp on
parted -s "$TMP_OUTPUT" unit MiB mkpart primary ext4 513 100%
PARTS=$(parted -m -s "$TMP_OUTPUT" unit B print)
ESP_OFFSET=$(printf '%s\n' "$PARTS" | awk -F: '$1 == "1" {gsub(/B/, "", $2); print $2}')
ESP_SIZE=$(printf '%s\n' "$PARTS" | awk -F: '$1 == "1" {gsub(/B/, "", $4); print $4}')
ROOT_OFFSET=$(printf '%s\n' "$PARTS" | awk -F: '$1 == "2" {gsub(/B/, "", $2); print $2}')
ROOT_SIZE=$(printf '%s\n' "$PARTS" | awk -F: '$1 == "2" {gsub(/B/, "", $4); print $4}')
[ -n "$ESP_OFFSET" ] && [ -n "$ESP_SIZE" ] && [ -n "$ROOT_OFFSET" ] && [ -n "$ROOT_SIZE" ] || fail "Could not parse generated GPT partition layout"

truncate -s "$ESP_SIZE" "$ESP_IMG"
mkfs.vfat -F 32 -n EFI -i "$ESP_ID" "$ESP_IMG" >/dev/null
mmd -i "$ESP_IMG" ::/EFI >/dev/null 2>&1 || true
mmd -i "$ESP_IMG" ::/EFI/BOOT >/dev/null 2>&1 || true
mmd -i "$ESP_IMG" ::/grub >/dev/null 2>&1 || true
mcopy -o -i "$ESP_IMG" "$BOOT_EFI" ::/EFI/BOOT/BOOTX64.EFI
mcopy -o -i "$ESP_IMG" "$GRUB_CFG" ::/grub/grub.cfg

log "Packing Gentoo root filesystem into ext4 image"
truncate -s "$ROOT_SIZE" "$ROOT_IMG"
mkfs.ext4 -F -U "$ROOT_UUID" -L gentoo-root -d "$ROOTFS" "$ROOT_IMG" >/dev/null

log "Embedding ESP and root partitions"
dd if="$ESP_IMG" of="$TMP_OUTPUT" bs=512 seek=$((ESP_OFFSET / 512)) conv=notrunc status=none
dd if="$ROOT_IMG" of="$TMP_OUTPUT" bs=512 seek=$((ROOT_OFFSET / 512)) conv=notrunc status=none
mv "$TMP_OUTPUT" "$OUTPUT"

log "Gentoo installed image written: $OUTPUT"
cat <<EOF

DONE: $OUTPUT

Image profile:
  distro: Gentoo $GENTOO_ARCH OpenRC (${GENTOO_STAGE3_BRANCH:-stable})
  desktop: ${ALPINE_USB_DESKTOP:-xfce}
  display manager: ${ALPINE_USB_DISPLAY_MANAGER:-auto}
  bootloader: GRUB removable UEFI (/EFI/BOOT/BOOTX64.EFI)
  root UUID: $ROOT_UUID
  user: ${ALPINE_USB_USER:-gentoo}

Write to USB:
  sudo dd if="$OUTPUT" of=/dev/sdX bs=16M iflag=fullblock status=progress conv=fsync

Replace /dev/sdX with USB device, not partition.
EOF
