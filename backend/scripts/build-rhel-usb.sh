#!/usr/bin/env bash
# Build a RHEL-family raw USB image using dnf --installroot. Linux host required.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Required tool not found: $1"; }

IMAGE_NAME="${IMAGE_NAME:-ledit-rhel.img}"
OUTPUT_PATH="${OUTPUT_PATH:-$IMAGE_NAME}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
RELEASE="${RHEL_USB_RELEASE:-9}"
PACKAGE_LIST="${RHEL_USB_PACKAGE_LIST:-@core kernel grub2-efi-x64 grub2-tools NetworkManager systemd passwd sudo}"
WORK_DIR="${RHEL_USB_WORK_DIR:-.work/rhel-build-$$}"
ROOTFS="$WORK_DIR/rootfs"
MNT="$WORK_DIR/mnt"
IMAGE="$WORK_DIR/image.raw"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)

if [ "$(uname -s)" = Darwin ] && [ "${RHEL_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop and try again."
  mkdir -p "$PROJECT_ROOT/.work"
  docker_env_file="$PROJECT_ROOT/.work/rhel-docker-env-$$"
  {
    printf '%s\n' \
      "RHEL_USB_BUILD_IN_DOCKER=1" \
      "IMAGE_NAME=$IMAGE_NAME" \
      "IMAGE_SIZE=$IMAGE_SIZE" \
      "RHEL_USB_WORK_DIR=/tmp/rhel-build" \
      "RHEL_USB_RELEASE=$RELEASE"
    if [ -n "$OUTPUT_PATH" ]; then
      mkdir -p "$(dirname "$OUTPUT_PATH")"
      output_dir=$(CDPATH= cd -- "$(dirname "$OUTPUT_PATH")" && pwd)
      output_base=$(basename "$OUTPUT_PATH")
      printf '%s\n' "OUTPUT_PATH=/out/$output_base"
    fi
    for name in RHEL_USB_DISTRO RHEL_USB_PACKAGE_LIST RHEL_USB_PROFILE RHEL_USB_USER RHEL_USB_PASSWORD_FILE RHEL_USB_ROOT_PASSWORD_FILE RHEL_USB_HOSTNAME RHEL_USB_TIMEZONE RHEL_USB_LOCALE RHEL_USB_CONSOLE_KEYMAP RHEL_USB_XKB_LAYOUT RHEL_USB_XKB_VARIANT RHEL_USB_XKB_MODEL RHEL_USB_DESKTOP RHEL_USB_TILING_WMS RHEL_USB_DEFAULT_SESSION RHEL_USB_DISPLAY_MANAGER RHEL_USB_NETWORK RHEL_USB_WIFI RHEL_USB_BLUETOOTH RHEL_USB_AUDIO RHEL_USB_BROWSER RHEL_USB_FIRMWARE RHEL_USB_BOOTLOADER RHEL_USB_KERNEL_FLAVOR RHEL_USB_BOOT_TIMEOUT RHEL_USB_AUTO_RESIZE RHEL_USB_EXTRA_PACKAGES; do
      eval "value=\${$name:-}"
      case "$name:$value" in *_FILE:$PROJECT_ROOT/*) value="/work/${value#"$PROJECT_ROOT"/}" ;; esac
      printf '%s=%s\n' "$name" "$value"
    done
  } > "$docker_env_file"
  docker_mounts=(-v "$PROJECT_ROOT:/work")
  if [ -n "$OUTPUT_PATH" ]; then
    docker_mounts+=(-v "$output_dir:/out")
  fi
  docker_name_args=()
  if [ -n "${RHEL_USB_DOCKER_NAME:-}" ]; then
    case "$RHEL_USB_DOCKER_NAME" in *[!A-Za-z0-9_.-]*|"") die "Invalid Docker container name: $RHEL_USB_DOCKER_NAME" ;; esac
    docker_name_args=(--name "$RHEL_USB_DOCKER_NAME")
  fi
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged --env-file "$docker_env_file" "${docker_mounts[@]}" -w /work rockylinux:9 bash -ceu '
    dnf -y install dnf-plugins-core parted dosfstools xfsprogs util-linux kpartx grub2-tools grub2-efi-x64 grub2-efi-x64-modules shim-x64 efibootmgr passwd systemd >/dev/null
    chmod +x backend/scripts/build-rhel-usb.sh backend/scripts/configure-rhel-usb.sh
    exec backend/scripts/build-rhel-usb.sh
  '
fi

[ "$(uname -s)" = Linux ] || die "RHEL-family image build currently requires a Linux host; use Docker/VM from macOS"
need dnf
need parted
need mkfs.vfat
need mkfs.xfs
need mount
need umount
need grub2-install
if [ "${RHEL_USB_BUILD_IN_DOCKER:-0}" = "1" ]; then
  [ -e /dev/loop-control ] || mknod /dev/loop-control c 10 237 || true
  for i in $(seq 0 15); do [ -e "/dev/loop$i" ] || mknod "/dev/loop$i" b 7 "$i" || true; done
fi

mkdir -p "$ROOTFS" "$MNT" "$(dirname "$OUTPUT_PATH")"
truncate -s "$IMAGE_SIZE" "$IMAGE"
parted -s "$IMAGE" mklabel gpt mkpart ESP fat32 1MiB 513MiB set 1 esp on mkpart root xfs 513MiB 100%
LOOP=$(losetup --find --partscan --show "$IMAGE")
MAPPED_WITH_KPARTX=0
cleanup() {
  set +e
  mountpoint -q "$MNT/boot/efi" && umount "$MNT/boot/efi"
  mountpoint -q "$MNT" && umount "$MNT"
  [ "$MAPPED_WITH_KPARTX" = 1 ] && kpartx -d "$LOOP" >/dev/null 2>&1 || true
  losetup -d "$LOOP" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
EFI_PART="${LOOP}p1"
ROOT_PART="${LOOP}p2"
if [ ! -b "$EFI_PART" ] || [ ! -b "$ROOT_PART" ]; then
  kpartx -avs "$LOOP" >/dev/null
  MAPPED_WITH_KPARTX=1
  EFI_PART="/dev/mapper/$(basename "$LOOP")p1"
  ROOT_PART="/dev/mapper/$(basename "$LOOP")p2"
fi
mkfs.vfat -F32 "$EFI_PART"
mkfs.xfs -f "$ROOT_PART"
mount "$ROOT_PART" "$MNT"
mkdir -p "$MNT/boot/efi"
mount "$EFI_PART" "$MNT/boot/efi"

dnf -y --releasever="$RELEASE" --installroot="$MNT" --setopt=install_weak_deps=False install $PACKAGE_LIST
"$SCRIPT_DIR/configure-rhel-usb.sh" "$MNT"
chroot "$MNT" /bin/sh -c "useradd -m -G wheel \"${RHEL_USB_USER:-linux}\" || true"
if [ -n "${RHEL_USB_PASSWORD_FILE:-}" ]; then PASS=$(cat "$RHEL_USB_PASSWORD_FILE"); else PASS="${RHEL_USB_PASSWORD:-linux}"; fi
if [ -n "${RHEL_USB_ROOT_PASSWORD_FILE:-}" ]; then ROOTPASS=$(cat "$RHEL_USB_ROOT_PASSWORD_FILE"); else ROOTPASS="${RHEL_USB_ROOT_PASSWORD:-$PASS}"; fi
printf '%s:%s\nroot:%s\n' "${RHEL_USB_USER:-linux}" "$PASS" "$ROOTPASS" | chroot "$MNT" chpasswd
chroot "$MNT" systemctl enable NetworkManager sshd linux-usb-firstboot.service || true
grub2-install --target=x86_64-efi --efi-directory="$MNT/boot/efi" --boot-directory="$MNT/boot" --removable --recheck --force "$LOOP"
UUID=$(blkid -s UUID -o value "$ROOT_PART")
cat > "$MNT/boot/grub2/grub.cfg" <<EOF
set default=0
set timeout=${RHEL_USB_BOOT_TIMEOUT:-3}
menuentry 'RHEL-family USB Linux' {
    linux /boot/vmlinuz root=UUID=$UUID ro quiet
    initrd /boot/initramfs
}
EOF
KERNEL=$(ls "$MNT/boot"/vmlinuz-* | head -n1)
INITRD=$(ls "$MNT/boot"/initramfs-*.img | head -n1)
cp "$KERNEL" "$MNT/boot/vmlinuz"
cp "$INITRD" "$MNT/boot/initramfs"
sync
cleanup
trap - EXIT INT TERM
mv "$IMAGE" "$OUTPUT_PATH"
echo "Image ready: $OUTPUT_PATH"
