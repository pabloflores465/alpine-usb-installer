#!/usr/bin/env bash
# Build a bootable Arch Linux USB disk image with pacstrap. Requires Linux root
# privileges and arch-install-scripts. macOS users should run this in an Arch
# builder VM/container with loop device support.
set -eu

IMAGE_NAME=${IMAGE_NAME:-arch-usb.img}
OUTPUT_PATH=${OUTPUT_PATH:-$IMAGE_NAME}
IMAGE_SIZE=${IMAGE_SIZE:-16G}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WORK_DIR=${WORK_DIR:-.work/arch-build}
ROOT_DIR=$WORK_DIR/root
MNT_DIR=$WORK_DIR/mnt
PACKAGES_FILE=$WORK_DIR/packages.txt
CONFIG_FILE=$WORK_DIR/config.env

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing required tool: $1" >&2; exit 1; }; }

if [ "$(uname -s)" = "Darwin" ] && [ "${ARCH_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "ERROR: Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  mkdir -p "$SCRIPT_DIR/.work"
  docker_env_file="$SCRIPT_DIR/.work/arch-docker-env-$$"
  {
    printf '%s\n' \
      "ARCH_USB_BUILD_IN_DOCKER=1" \
      "IMAGE_NAME=$IMAGE_NAME" \
      "IMAGE_SIZE=$IMAGE_SIZE"
    if [ -n "$OUTPUT_PATH" ]; then
      mkdir -p "$(dirname "$OUTPUT_PATH")"
      output_dir=$(CDPATH= cd -- "$(dirname "$OUTPUT_PATH")" && pwd)
      output_base=$(basename "$OUTPUT_PATH")
      printf '%s\n' "OUTPUT_PATH=/out/$output_base"
    fi
    for name in ALPINE_USB_USER ALPINE_USB_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_HOSTNAME ALPINE_USB_TIMEZONE ALPINE_USB_LOCALE ALPINE_USB_LANGUAGE ALPINE_USB_CONSOLE_KEYMAP ALPINE_USB_XKB_LAYOUT ALPINE_USB_XKB_VARIANT ALPINE_USB_XKB_MODEL ALPINE_USB_DESKTOP ALPINE_USB_TILING_WMS ALPINE_USB_DEFAULT_SESSION ALPINE_USB_DISPLAY_MANAGER ALPINE_USB_NETWORK ALPINE_USB_WIFI ALPINE_USB_BLUETOOTH ALPINE_USB_AUDIO ALPINE_USB_BROWSER ALPINE_USB_FIRMWARE ALPINE_USB_LEGACY_X11_DRIVERS ALPINE_USB_BOOTLOADER ALPINE_USB_KERNEL_FLAVOR ALPINE_USB_BOOT_TIMEOUT ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE ALPINE_USB_AUTO_RESIZE ALPINE_USB_EXTRA_PACKAGES ALPINE_USB_PROFILE ARCH_USB_BRANCH; do
      eval "value=\${$name:-}"
      case "$name:$value" in
        *_FILE:$SCRIPT_DIR/*) value="/work/${value#"$SCRIPT_DIR"/}" ;;
      esac
      printf '%s=%s\n' "$name" "$value"
    done
  } > "$docker_env_file"
  docker_mounts=(-v "$SCRIPT_DIR:/work")
  if [ -n "$OUTPUT_PATH" ]; then
    docker_mounts+=(-v "$output_dir:/out")
  fi
  docker_name_args=()
  if [ -n "${ARCH_USB_DOCKER_NAME:-}" ]; then
    case "$ARCH_USB_DOCKER_NAME" in *[!A-Za-z0-9_.-]*|"") echo "ERROR: invalid Docker container name: $ARCH_USB_DOCKER_NAME" >&2; exit 1 ;; esac
    docker_name_args=(--name "$ARCH_USB_DOCKER_NAME")
  fi
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged --security-opt seccomp=unconfined --env-file "$docker_env_file" "${docker_mounts[@]}" -w /work archlinux:latest bash -ceu '
    grep -qxF DisableSandbox /etc/pacman.conf || printf "\nDisableSandbox\n" >> /etc/pacman.conf
    cat >/etc/pacman.d/mirrorlist <<EOF_MIRRORS
Server = https://geo.mirror.pkgbuild.com/\$repo/os/\$arch
Server = https://mirrors.kernel.org/archlinux/\$repo/os/\$arch
Server = https://mirror.rackspace.com/archlinux/\$repo/os/\$arch
EOF_MIRRORS
    pacman -Sy --noconfirm --needed python arch-install-scripts dosfstools e2fsprogs util-linux grub efibootmgr sudo systemd multipath-tools >/dev/null
    chmod +x build-arch-usb.sh configure-arch-usb.sh
    exec ./build-arch-usb.sh
  '
fi

for tool in python3 pacstrap arch-chroot sfdisk losetup mkfs.fat mkfs.ext4 mount umount; do need "$tool"; done
[ "$(id -u)" = 0 ] || { echo "ERROR: Arch build requires root for loop mounts and pacstrap" >&2; exit 1; }
if [ "${ARCH_USB_BUILD_IN_DOCKER:-0}" = "1" ]; then
  [ -e /dev/loop-control ] || mknod /dev/loop-control c 10 237 || true
  for i in $(seq 0 15); do [ -e "/dev/loop$i" ] || mknod "/dev/loop$i" b 7 "$i" || true; done
fi

mkdir -p "$WORK_DIR" "$ROOT_DIR" "$MNT_DIR"
ARCH_USB_PACKAGES_FILE=$PACKAGES_FILE ARCH_USB_CONFIG_FILE=$CONFIG_FILE ROOT_DIR=$ROOT_DIR ./configure-arch-usb.sh

rm -f "$OUTPUT_PATH"
truncate -s "$IMAGE_SIZE" "$OUTPUT_PATH"
loop=$(losetup --find --show --partscan "$OUTPUT_PATH")
MAPPED_WITH_KPARTX=0
cleanup() {
  set +e
  for mp in "$MNT_DIR/run" "$MNT_DIR/sys" "$MNT_DIR/proc" "$MNT_DIR/dev" "$MNT_DIR/boot" "$MNT_DIR"; do
    mountpoint -q "$mp" && umount -R "$mp" >/dev/null 2>&1
  done
  [ "$MAPPED_WITH_KPARTX" = 1 ] && kpartx -d "$loop" >/dev/null 2>&1 || true
  losetup -d "$loop" 2>/dev/null
}
trap cleanup EXIT INT TERM

sfdisk "$loop" <<'EOF'
label: gpt
,512M,U
,,L
EOF
if [ "${ARCH_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then partprobe "$loop" || true; fi
sleep 1
boot_part="${loop}p1"
root_part="${loop}p2"
if [ ! -b "$boot_part" ] || [ ! -b "$root_part" ]; then
  kpartx -avs "$loop" >/dev/null
  MAPPED_WITH_KPARTX=1
  boot_part="/dev/mapper/$(basename "$loop")p1"
  root_part="/dev/mapper/$(basename "$loop")p2"
fi
mkfs.fat -F32 "$boot_part"
mkfs.ext4 -F "$root_part"
mount "$root_part" "$MNT_DIR"
mkdir -p "$MNT_DIR/boot"
mount "$boot_part" "$MNT_DIR/boot"

pacstrap -K "$MNT_DIR" $(tr '\n' ' ' < "$PACKAGES_FILE")
genfstab -U "$MNT_DIR" >> "$MNT_DIR/etc/fstab"
cp "$CONFIG_FILE" "$MNT_DIR/root/arch-usb-config.env"
mkdir -p "$MNT_DIR/dev" "$MNT_DIR/proc" "$MNT_DIR/sys" "$MNT_DIR/run"
mount --rbind /dev "$MNT_DIR/dev"
mount -t proc proc "$MNT_DIR/proc"
mount --rbind /sys "$MNT_DIR/sys" || true
mount --rbind /run "$MNT_DIR/run" || true

chroot "$MNT_DIR" /bin/bash -eu <<'CHROOT'
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
