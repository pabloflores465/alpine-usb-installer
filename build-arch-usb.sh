#!/bin/sh
# Build a bootable Arch Linux USB disk image with pacstrap. Requires Linux root
# privileges and arch-install-scripts. macOS users should run this in an Arch
# builder VM/container with loop device support.
set -eu

IMAGE_NAME=${IMAGE_NAME:-arch-usb.img}
OUTPUT_PATH=${OUTPUT_PATH:-$IMAGE_NAME}
IMAGE_SIZE=${IMAGE_SIZE:-16G}
WORK_DIR=${WORK_DIR:-.work/arch-build}
ROOT_DIR=$WORK_DIR/root
MNT_DIR=$WORK_DIR/mnt
PACKAGES_FILE=$WORK_DIR/packages.txt
CONFIG_FILE=$WORK_DIR/config.env

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing required tool: $1" >&2; exit 1; }; }
for tool in python3 pacstrap arch-chroot sfdisk losetup mkfs.fat mkfs.ext4 mount umount; do need "$tool"; done
[ "$(id -u)" = 0 ] || { echo "ERROR: Arch build requires root for loop mounts and pacstrap" >&2; exit 1; }

mkdir -p "$WORK_DIR" "$ROOT_DIR" "$MNT_DIR"
ARCH_USB_PACKAGES_FILE=$PACKAGES_FILE ARCH_USB_CONFIG_FILE=$CONFIG_FILE ROOT_DIR=$ROOT_DIR ./configure-arch-usb.sh

rm -f "$OUTPUT_PATH"
truncate -s "$IMAGE_SIZE" "$OUTPUT_PATH"
loop=$(losetup --find --show --partscan "$OUTPUT_PATH")
cleanup() {
  set +e
  mountpoint -q "$MNT_DIR/boot" && umount "$MNT_DIR/boot"
  mountpoint -q "$MNT_DIR" && umount "$MNT_DIR"
  losetup -d "$loop" 2>/dev/null
}
trap cleanup EXIT INT TERM

sfdisk "$loop" <<'EOF'
label: gpt
,512M,U
,,L
EOF
partprobe "$loop" || true
sleep 1
mkfs.fat -F32 "${loop}p1"
mkfs.ext4 -F "${loop}p2"
mount "${loop}p2" "$MNT_DIR"
mkdir -p "$MNT_DIR/boot"
mount "${loop}p1" "$MNT_DIR/boot"

pacstrap -K "$MNT_DIR" $(tr '\n' ' ' < "$PACKAGES_FILE")
genfstab -U "$MNT_DIR" >> "$MNT_DIR/etc/fstab"
cp "$CONFIG_FILE" "$MNT_DIR/root/arch-usb-config.env"

arch-chroot "$MNT_DIR" /bin/bash -eu <<'CHROOT'
source /root/arch-usb-config.env || true
ln -sf "/usr/share/zoneinfo/${ALPINE_USB_TIMEZONE:-UTC}" /etc/localtime || true
hwclock --systohc || true
echo "${ALPINE_USB_HOSTNAME:-arch-usb}" > /etc/hostname
sed -i "s/^#\(${ALPINE_USB_LOCALE:-en_US.UTF-8} UTF-8\)/\1/" /etc/locale.gen || true
locale-gen || true
echo "LANG=${ALPINE_USB_LOCALE:-en_US.UTF-8}" > /etc/locale.conf
echo "KEYMAP=${ALPINE_USB_CONSOLE_KEYMAP:-us}" > /etc/vconsole.conf
useradd -m -G wheel -s /bin/bash "${ALPINE_USB_USER:-arch}" || true
echo "%wheel ALL=(ALL:ALL) ALL" > /etc/sudoers.d/10-wheel
chmod 0440 /etc/sudoers.d/10-wheel
systemctl enable NetworkManager 2>/dev/null || true
case "${ALPINE_USB_DISPLAY_MANAGER:-auto}" in
  lightdm|sddm|gdm|lxdm) systemctl enable "${ALPINE_USB_DISPLAY_MANAGER}" 2>/dev/null || true ;;
esac
if [ "${ALPINE_USB_BOOTLOADER:-grub}" = grub ]; then
  grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=ARCHUSB --removable
  grub-mkconfig -o /boot/grub/grub.cfg
else
  bootctl install --esp-path=/boot || true
fi
CHROOT

cleanup
trap - EXIT INT TERM
printf 'Arch image ready: %s\n' "$OUTPUT_PATH"
