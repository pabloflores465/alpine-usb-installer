#!/bin/sh
# Build a RHEL-family raw USB image using dnf --installroot. Linux host required.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Required tool not found: $1"; }

IMAGE_NAME="${IMAGE_NAME:-rhel-usb.img}"
OUTPUT_PATH="${OUTPUT_PATH:-$IMAGE_NAME}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
RELEASE="${RHEL_USB_RELEASE:-9}"
PACKAGE_LIST="${RHEL_USB_PACKAGE_LIST:-@core kernel grub2-efi-x64 grub2-tools NetworkManager systemd passwd sudo}"
WORK_DIR="${RHEL_USB_WORK_DIR:-.work/rhel-build-$$}"
ROOTFS="$WORK_DIR/rootfs"
MNT="$WORK_DIR/mnt"
IMAGE="$WORK_DIR/image.raw"

[ "$(uname -s)" = Linux ] || die "RHEL-family image build currently requires a Linux host; use Docker/VM from macOS"
need dnf
need parted
need mkfs.vfat
need mkfs.xfs
need mount
need umount
need grub2-install

mkdir -p "$ROOTFS" "$MNT" "$(dirname "$OUTPUT_PATH")"
truncate -s "$IMAGE_SIZE" "$IMAGE"
parted -s "$IMAGE" mklabel gpt mkpart ESP fat32 1MiB 513MiB set 1 esp on mkpart root xfs 513MiB 100%
LOOP=$(losetup --find --partscan --show "$IMAGE")
cleanup() {
  set +e
  mountpoint -q "$MNT/boot/efi" && umount "$MNT/boot/efi"
  mountpoint -q "$MNT" && umount "$MNT"
  losetup -d "$LOOP" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
mkfs.vfat -F32 "${LOOP}p1"
mkfs.xfs -f "${LOOP}p2"
mount "${LOOP}p2" "$MNT"
mkdir -p "$MNT/boot/efi"
mount "${LOOP}p1" "$MNT/boot/efi"

dnf -y --releasever="$RELEASE" --installroot="$MNT" --setopt=install_weak_deps=False install $PACKAGE_LIST
./configure-rhel-usb.sh "$MNT"
chroot "$MNT" /bin/sh -c "useradd -m -G wheel \"${RHEL_USB_USER:-linux}\" || true"
if [ -n "${RHEL_USB_PASSWORD_FILE:-}" ]; then PASS=$(cat "$RHEL_USB_PASSWORD_FILE"); else PASS="${RHEL_USB_PASSWORD:-linux}"; fi
if [ -n "${RHEL_USB_ROOT_PASSWORD_FILE:-}" ]; then ROOTPASS=$(cat "$RHEL_USB_ROOT_PASSWORD_FILE"); else ROOTPASS="${RHEL_USB_ROOT_PASSWORD:-$PASS}"; fi
printf '%s:%s\nroot:%s\n' "${RHEL_USB_USER:-linux}" "$PASS" "$ROOTPASS" | chroot "$MNT" chpasswd
chroot "$MNT" systemctl enable NetworkManager sshd linux-usb-firstboot.service || true
grub2-install --target=x86_64-efi --efi-directory="$MNT/boot/efi" --boot-directory="$MNT/boot" --removable --recheck "$LOOP"
UUID=$(blkid -s UUID -o value "${LOOP}p2")
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
