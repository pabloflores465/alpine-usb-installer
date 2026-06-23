#!/usr/bin/env bash
# Build a configurable, preinstalled Alpine Linux USB image.
set -euo pipefail

IMAGE_NAME="${IMAGE_NAME:-ledit.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
ALPINE_BRANCH="${ALPINE_BRANCH:-latest-stable}"
ARCH="${ARCH:-x86_64}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/.work}"
MAKE_VM_IMAGE="$WORK_DIR/alpine-make-vm-image.uefi"
MAKE_VM_IMAGE_SOURCE="$WORK_DIR/alpine-make-vm-image.uefi.source"
MAKE_VM_IMAGE_COMMIT="dda77715d4dfe8704eb55f310dc1318920d5fd75"
MAKE_VM_IMAGE_SHA256="860b2b9efb73869085ba0a9401555ff0eac29072d102ffd39884ddb90aedc2f4"
MAKE_VM_IMAGE_URL="https://raw.githubusercontent.com/alpinelinux/alpine-make-vm-image/$MAKE_VM_IMAGE_COMMIT/alpine-make-vm-image"
DOCKER_IMAGE="${LEDIT_USB_DOCKER_IMAGE:-alpine:3.22@sha256:310c62b5e7ca5b08167e4384c68db0fd2905dd9c7493756d356e893909057601}"
BUILDER_IMAGE="${LEDIT_USB_BUILDER_IMAGE:-ledit-linux-builder:3.22-amd64}"
BUILDER_DOCKERFILE="${LEDIT_USB_BUILDER_DOCKERFILE:-$SCRIPT_DIR/scripts/Dockerfile.builder}"

LEDIT_USB_KERNEL_FLAVOR="${LEDIT_USB_KERNEL_FLAVOR:-${KERNEL_FLAVOR:-lts}}"
LEDIT_USB_BOOTLOADER="${LEDIT_USB_BOOTLOADER:-${BOOTLOADER:-grub}}"
LEDIT_USB_ROOTFS="${LEDIT_USB_ROOTFS:-ext4}"
LEDIT_USB_BOOT_TIMEOUT="${LEDIT_USB_BOOT_TIMEOUT:-3}"
LEDIT_USB_INITFS_FEATURES="${LEDIT_USB_INITFS_FEATURES:-ata base ext4 kms mmc nvme scsi usb virtio}"
LEDIT_USB_USER="${LEDIT_USB_USER:-alpine}"

LEDIT_USB_BOOTLOADER="$(printf '%s' "$LEDIT_USB_BOOTLOADER" | tr '[:upper:]' '[:lower:]')"
[ "$LEDIT_USB_BOOTLOADER" = "systemdboot" ] && LEDIT_USB_BOOTLOADER="systemd-boot"
case "$LEDIT_USB_BOOTLOADER" in grub|systemd-boot) ;; *) echo "Invalid bootloader: $LEDIT_USB_BOOTLOADER" >&2; exit 1 ;; esac
case "$LEDIT_USB_KERNEL_FLAVOR" in lts|stable) ;; *) echo "Invalid kernel flavor: $LEDIT_USB_KERNEL_FLAVOR" >&2; exit 1 ;; esac
case "$LEDIT_USB_ROOTFS" in ext4) ;; *) echo "Only ext4 rootfs is supported by this USB installer" >&2; exit 1 ;; esac
if [[ "$ALPINE_BRANCH" != "latest-stable" && "$ALPINE_BRANCH" != "edge" && ! "$ALPINE_BRANCH" =~ ^v[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid Alpine branch: $ALPINE_BRANCH" >&2
  exit 1
fi
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid image name: $IMAGE_NAME" >&2
  exit 1
fi
if [ -n "$OUTPUT_PATH" ]; then
  case "$OUTPUT_PATH" in
    /*) ;;
    *) echo "OUTPUT_PATH must be absolute: $OUTPUT_PATH" >&2; exit 1 ;;
  esac
fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\''/g")"
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

verify_sha256() {
  local file="$1"
  local expected="$2"
  local actual
  actual="$(sha256_file "$file")"
  [ "$actual" = "$expected" ] || {
    echo "Checksum mismatch for $file" >&2
    echo "  expected: $expected" >&2
    echo "  actual:   $actual" >&2
    return 1
  }
}

mkdir -p "$WORK_DIR"
chmod 700 "$WORK_DIR" 2>/dev/null || true

# macOS cannot run the Linux/NBD build natively. Run it in a privileged Docker
# container. Prefer a cached builder image so repeated builds do not reinstall
# the same build tools every time; fall back to the pinned Alpine base image if
# the Dockerfile is unavailable or LEDIT_USB_SKIP_BUILDER_CACHE=1.
if [ "$(uname -s)" = "Darwin" ] && [ "${LEDIT_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found. Install Docker Desktop and try again." >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start Docker Desktop and try again." >&2
    exit 1
  fi

  pass_env=(
    IMAGE_NAME OUTPUT_PATH IMAGE_SIZE ALPINE_BRANCH ARCH
    LEDIT_USB_USER LEDIT_USB_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_HOSTNAME
    LEDIT_USB_TIMEZONE LEDIT_USB_LOCALE LEDIT_USB_LANGUAGE
    LEDIT_USB_CONSOLE_KEYMAP LEDIT_USB_XKB_LAYOUT LEDIT_USB_XKB_VARIANT LEDIT_USB_XKB_MODEL
    LEDIT_USB_DESKTOP LEDIT_USB_TILING_WMS LEDIT_USB_DEFAULT_SESSION LEDIT_USB_DISPLAY_MANAGER
    LEDIT_USB_NETWORK LEDIT_USB_WIFI LEDIT_USB_BLUETOOTH LEDIT_USB_AUDIO LEDIT_USB_BROWSER
    LEDIT_USB_FIRMWARE LEDIT_USB_LEGACY_X11_DRIVERS LEDIT_USB_BOOTLOADER LEDIT_USB_KERNEL_FLAVOR LEDIT_USB_ROOTFS
    LEDIT_USB_BOOT_TIMEOUT LEDIT_USB_INITFS_FEATURES LEDIT_USB_SYSTEMD_BOOT_CONSOLE_MODE
    LEDIT_USB_AUTO_RESIZE LEDIT_USB_EXTRA_PACKAGES LEDIT_USB_PROFILE
  )
  docker_env=(-e LEDIT_USB_BUILD_IN_DOCKER=1)
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  docker_name_args=()
  if [ -n "${LEDIT_USB_DOCKER_NAME:-}" ]; then
    docker_name_args=(--name "$LEDIT_USB_DOCKER_NAME")
  fi
  for name in "${pass_env[@]}"; do
    value="${!name-}"
    if [ "$name" = "OUTPUT_PATH" ] && [ -n "$value" ]; then
      mkdir -p "$(dirname "$value")"
      output_dir="$(cd "$(dirname "$value")" && pwd -P)"
      output_base="$(basename "$value")"
      docker_mounts+=( -v "$output_dir:/out" )
      docker_env+=( -e "OUTPUT_PATH=/out/$output_base" )
      continue
    fi
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$SCRIPT_DIR/"* ]]; then
      value="/work/${value#"$SCRIPT_DIR"/}"
    fi
    docker_env+=( -e "$name=$value" )
  done

  if [ "${LEDIT_USB_SKIP_BUILDER_CACHE:-0}" != "1" ] && [ -f "$BUILDER_DOCKERFILE" ]; then
    if [ "${LEDIT_USB_REBUILD_BUILDER:-0}" = "1" ] || ! docker image inspect "$BUILDER_IMAGE" >/dev/null 2>&1; then
      echo "Building cached LEDIT builder image ($BUILDER_IMAGE)..."
      docker build --platform linux/amd64 -f "$BUILDER_DOCKERFILE" -t "$BUILDER_IMAGE" "$(dirname "$BUILDER_DOCKERFILE")"
    fi
    echo "Starting Docker build container with cached LEDIT build tools ($BUILDER_IMAGE)..."
    exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
      "${docker_env[@]}" \
      "${docker_mounts[@]}" \
      -w /work \
      "$BUILDER_IMAGE" \
      sh -ceu 'chmod +x build-alpine-usb.sh configure-alpine-usb.sh; exec ./build-alpine-usb.sh'
  fi

  echo "Starting fresh Docker build container with Alpine build tools ($DOCKER_IMAGE)..."
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
    "${docker_env[@]}" \
    "${docker_mounts[@]}" \
    -w /work \
    "$DOCKER_IMAGE" \
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
need mdir

if [ ! -f "$MAKE_VM_IMAGE_SOURCE" ] || ! verify_sha256 "$MAKE_VM_IMAGE_SOURCE" "$MAKE_VM_IMAGE_SHA256" >/dev/null 2>&1; then
  echo "Downloading pinned alpine-make-vm-image ($MAKE_VM_IMAGE_COMMIT)..."
  tmp_source="$MAKE_VM_IMAGE_SOURCE.tmp.$$"
  rm -f "$tmp_source"
  curl --fail --location --proto '=https' --tlsv1.2 "$MAKE_VM_IMAGE_URL" -o "$tmp_source"
  verify_sha256 "$tmp_source" "$MAKE_VM_IMAGE_SHA256"
  mv "$tmp_source" "$MAKE_VM_IMAGE_SOURCE"
fi

if [ ! -x "$MAKE_VM_IMAGE" ] || [ "$MAKE_VM_IMAGE_SOURCE" -nt "$MAKE_VM_IMAGE" ]; then
  cp "$MAKE_VM_IMAGE_SOURCE" "$MAKE_VM_IMAGE"
  chmod +x "$MAKE_VM_IMAGE"
fi

chmod +x "$SCRIPT_DIR/configure-alpine-usb.sh"

# Docker Desktop/macOS can be slow or unable to expose NBD partition nodes
# (/dev/nbdXp1, /dev/nbdXp2). Patch alpine-make-vm-image idempotently to force
# a partition re-read and fall back to kpartx mapper nodes (/dev/mapper/nbdXpN).
python3 - <<'PY'
from pathlib import Path
import re
p = Path('.work/alpine-make-vm-image.uefi')
s = p.read_text()

if 'kpartx -d "$disk_dev"' not in s:
    s = s.replace('''\tif [ "$disk_dev" ] && ! [ -b "$IMAGE_FILE" ]; then\n\t\tqemu-nbd --disconnect "$disk_dev" \\\n\t\t\t|| die "Failed to disconnect $disk_dev; disconnect it manually"\n\tfi''', '''\tif [ "$disk_dev" ] && ! [ -b "$IMAGE_FILE" ]; then\n\t\tkpartx -d "$disk_dev" >/dev/null 2>&1 || true\n\t\tqemu-nbd --disconnect "$disk_dev" \\\n\t\t\t|| die "Failed to disconnect $disk_dev; disconnect it manually"\n\tfi''')

if 'Docker Desktop can be slow' not in s:
    old = r'''\t# This is needed when running in a container(?:.|\n)*?\tsettle_dev_node "\$root_dev" \|\| die "system didn't create \$root_dev node"'''
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

read_image_meta() {
  local image="$1"
  python3 - "$image" <<'PY'
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
}

install_grub_removable_bootloader() {
  # Many real PCs only list USB media as bootable when the removable-media
  # fallback path exists: /EFI/BOOT/BOOTX64.EFI.
  local image="$1"
  local fallback="$SCRIPT_DIR/efi-fallback/BOOTX64.EFI"
  local standalone_cfg="$WORK_DIR/grub-standalone.cfg"
  local esp_offset root_uuid grub_cfg modules_csv

  eval "$(read_image_meta "$image")"
  modules_csv="$(printf '%s' "$LEDIT_USB_INITFS_FEATURES" | tr ' ' ',')"

  grub_cfg="$WORK_DIR/grub-usb.cfg"
  mkdir -p "$SCRIPT_DIR/efi-fallback"
  cat > "$grub_cfg" <<EOF
set default=0
set timeout=$LEDIT_USB_BOOT_TIMEOUT
set timeout_style=menu

insmod part_gpt
insmod fat
insmod gzio
insmod linux
insmod search_fs_file
search --no-floppy --file --set=root /vmlinuz-$LEDIT_USB_KERNEL_FLAVOR

menuentry 'Alpine Linux USB' {
    linux /vmlinuz-$LEDIT_USB_KERNEL_FLAVOR root=UUID=$root_uuid ro rootfstype=$LEDIT_USB_ROOTFS rootwait rootdelay=5 modules=$modules_csv console=tty0
    initrd /initramfs-$LEDIT_USB_KERNEL_FLAVOR
}

menuentry 'Alpine Linux USB (safe graphics)' {
    linux /vmlinuz-$LEDIT_USB_KERNEL_FLAVOR root=UUID=$root_uuid ro rootfstype=$LEDIT_USB_ROOTFS rootwait rootdelay=5 modules=$modules_csv console=tty0 nomodeset
    initrd /initramfs-$LEDIT_USB_KERNEL_FLAVOR
}
EOF

  need grub-mkstandalone
  cat > "$standalone_cfg" <<EOF
insmod part_gpt
insmod fat
insmod search_fs_file
search --no-floppy --file --set=esp /grub/grub.cfg
# Keep prefix on the standalone memdisk so GRUB can load embedded modules.
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
  echo "Installed removable GRUB UEFI bootloader: /EFI/BOOT/BOOTX64.EFI"
  echo "Installed USB GRUB config: /grub/grub.cfg (root UUID $root_uuid)"
}

validate_systemd_bootloader() {
  local image="$1"
  local esp_offset root_uuid efi_name
  eval "$(read_image_meta "$image")"
  case "$ARCH" in
    x86_64) efi_name="BOOTX64.EFI" ;;
    x86) efi_name="BOOTIA32.EFI" ;;
    aarch64) efi_name="BOOTAA64.EFI" ;;
    armv7|armhf) efi_name="BOOTARM.EFI" ;;
    *) efi_name="BOOTX64.EFI" ;;
  esac
  mdir -i "${image}@@${esp_offset}" ::/EFI/BOOT/"$efi_name" >/dev/null \
    || { echo "systemd-boot fallback /EFI/BOOT/$efi_name was not created" >&2; exit 1; }
  mdir -i "${image}@@${esp_offset}" ::/loader/entries/alpine.conf >/dev/null \
    || { echo "systemd-boot loader entry was not created" >&2; exit 1; }
  echo "Validated removable systemd-boot UEFI bootloader: /EFI/BOOT/$efi_name (root UUID $root_uuid)"
}

cat > "$SCRIPT_DIR/repositories" <<EOF
https://dl-cdn.alpinelinux.org/alpine/$ALPINE_BRANCH/main
https://dl-cdn.alpinelinux.org/alpine/$ALPINE_BRANCH/community
EOF

cd "$SCRIPT_DIR"

BUILD_IMAGE_PATH="$SCRIPT_DIR/$IMAGE_NAME"
if [ -n "$OUTPUT_PATH" ]; then
  BUILD_IMAGE_PATH="$OUTPUT_PATH"
fi
mkdir -p "$(dirname "$BUILD_IMAGE_PATH")"

# Always rebuild from a clean image. Reusing an old raw image can leave stale
# filesystem signatures and confuse NBD partition node creation.
rm -f "$BUILD_IMAGE_PATH"

CONFIGURE_SCRIPT_FOR_BUILD="$SCRIPT_DIR/configure-alpine-usb.sh"
SECRET_CONFIGURE_SCRIPT=""
cleanup_secret_configure() {
  [ -n "$SECRET_CONFIGURE_SCRIPT" ] && rm -f "$SECRET_CONFIGURE_SCRIPT"
}
trap cleanup_secret_configure EXIT INT TERM
if [ -n "${LEDIT_USB_PASSWORD_FILE:-}" ] || [ -n "${LEDIT_USB_ROOT_PASSWORD_FILE:-}" ]; then
  password_value=""
  root_password_value=""
  [ -n "${LEDIT_USB_PASSWORD_FILE:-}" ] && password_value="$(cat "$LEDIT_USB_PASSWORD_FILE")"
  [ -n "${LEDIT_USB_ROOT_PASSWORD_FILE:-}" ] && root_password_value="$(cat "$LEDIT_USB_ROOT_PASSWORD_FILE")"
  [ -n "$root_password_value" ] || root_password_value="$password_value"
  SECRET_CONFIGURE_SCRIPT="$WORK_DIR/configure-ledit-linux-secure-$$.sh"
  {
    printf '#!/bin/sh\n'
    printf 'LEDIT_USB_PASSWORD=%s\n' "$(shell_quote "$password_value")"
    printf 'LEDIT_USB_ROOT_PASSWORD=%s\n' "$(shell_quote "$root_password_value")"
    cat "$SCRIPT_DIR/configure-alpine-usb.sh"
  } > "$SECRET_CONFIGURE_SCRIPT"
  chmod 700 "$SECRET_CONFIGURE_SCRIPT"
  CONFIGURE_SCRIPT_FOR_BUILD="$SECRET_CONFIGURE_SCRIPT"
fi

# raw image: easiest to dd to USB.
sudo env \
  LEDIT_USB_USER="$LEDIT_USB_USER" \
  LEDIT_USB_HOSTNAME="${LEDIT_USB_HOSTNAME:-}" \
  LEDIT_USB_TIMEZONE="${LEDIT_USB_TIMEZONE:-}" \
  LEDIT_USB_LOCALE="${LEDIT_USB_LOCALE:-}" \
  LEDIT_USB_LANGUAGE="${LEDIT_USB_LANGUAGE:-}" \
  LEDIT_USB_CONSOLE_KEYMAP="${LEDIT_USB_CONSOLE_KEYMAP:-}" \
  LEDIT_USB_XKB_LAYOUT="${LEDIT_USB_XKB_LAYOUT:-}" \
  LEDIT_USB_XKB_VARIANT="${LEDIT_USB_XKB_VARIANT:-}" \
  LEDIT_USB_XKB_MODEL="${LEDIT_USB_XKB_MODEL:-}" \
  LEDIT_USB_DESKTOP="${LEDIT_USB_DESKTOP:-}" \
  LEDIT_USB_TILING_WMS="${LEDIT_USB_TILING_WMS:-}" \
  LEDIT_USB_DEFAULT_SESSION="${LEDIT_USB_DEFAULT_SESSION:-}" \
  LEDIT_USB_DISPLAY_MANAGER="${LEDIT_USB_DISPLAY_MANAGER:-}" \
  LEDIT_USB_NETWORK="${LEDIT_USB_NETWORK:-}" \
  LEDIT_USB_WIFI="${LEDIT_USB_WIFI:-}" \
  LEDIT_USB_BLUETOOTH="${LEDIT_USB_BLUETOOTH:-}" \
  LEDIT_USB_AUDIO="${LEDIT_USB_AUDIO:-}" \
  LEDIT_USB_BROWSER="${LEDIT_USB_BROWSER:-}" \
  LEDIT_USB_FIRMWARE="${LEDIT_USB_FIRMWARE:-}" \
  LEDIT_USB_LEGACY_X11_DRIVERS="${LEDIT_USB_LEGACY_X11_DRIVERS:-}" \
  LEDIT_USB_PROFILE="${LEDIT_USB_PROFILE:-}" \
  LEDIT_USB_BOOTLOADER="$LEDIT_USB_BOOTLOADER" \
  LEDIT_USB_KERNEL_FLAVOR="$LEDIT_USB_KERNEL_FLAVOR" \
  LEDIT_USB_ROOTFS="$LEDIT_USB_ROOTFS" \
  LEDIT_USB_BOOT_TIMEOUT="$LEDIT_USB_BOOT_TIMEOUT" \
  LEDIT_USB_INITFS_FEATURES="$LEDIT_USB_INITFS_FEATURES" \
  LEDIT_USB_SYSTEMD_BOOT_CONSOLE_MODE="${LEDIT_USB_SYSTEMD_BOOT_CONSOLE_MODE:-}" \
  LEDIT_USB_AUTO_RESIZE="${LEDIT_USB_AUTO_RESIZE:-}" \
  LEDIT_USB_EXTRA_PACKAGES="${LEDIT_USB_EXTRA_PACKAGES:-}" \
  "$MAKE_VM_IMAGE" \
  --image-format raw \
  --image-size "$IMAGE_SIZE" \
  --arch "$ARCH" \
  --boot-mode UEFI \
  --kernel-flavor "$LEDIT_USB_KERNEL_FLAVOR" \
  --rootfs "$LEDIT_USB_ROOTFS" \
  --initfs-features "$LEDIT_USB_INITFS_FEATURES" \
  --repositories-file "$SCRIPT_DIR/repositories" \
  --script-chroot \
  "$BUILD_IMAGE_PATH" \
  "$CONFIGURE_SCRIPT_FOR_BUILD"

if [ -f "$BUILD_IMAGE_PATH" ]; then
  sudo chown "$(id -u):$(id -g)" "$BUILD_IMAGE_PATH" 2>/dev/null || true
fi

case "$LEDIT_USB_BOOTLOADER" in
  grub) install_grub_removable_bootloader "$BUILD_IMAGE_PATH" ;;
  systemd-boot) validate_systemd_bootloader "$BUILD_IMAGE_PATH" ;;
esac

cat <<EOF

DONE: $BUILD_IMAGE_PATH

Image profile:
  desktop: ${LEDIT_USB_DESKTOP:-xfce}
  tiling WMs: ${LEDIT_USB_TILING_WMS:-none}
  display manager: ${LEDIT_USB_DISPLAY_MANAGER:-auto}
  bootloader: $LEDIT_USB_BOOTLOADER
  kernel: linux-$LEDIT_USB_KERNEL_FLAVOR
  auto-resize root on first boot: ${LEDIT_USB_AUTO_RESIZE:-1}
  user: $LEDIT_USB_USER

Write to USB:
  lsblk
  sudo dd if="$BUILD_IMAGE_PATH" of=/dev/sdX bs=16M iflag=fullblock status=progress conv=fsync

Replace /dev/sdX with USB device, not partition. Example /dev/sdb, NOT /dev/sdb1.
EOF
