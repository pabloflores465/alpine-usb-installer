#!/usr/bin/env bash
# Build or dry-run a Fedora USB image plan. Full installroot image creation is implemented for Linux hosts
# with dnf, parted, dosfstools and e2fsprogs; macOS should use Docker/VM support in a future adapter.
set -euo pipefail

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" || "${FEDORA_USB_DRY_RUN:-0}" =~ ^(1|yes|true|on)$ ]]; then
  DRY_RUN=1
fi

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing required tool: $1"; }

safe_token() {
  local name="$1" value="$2"
  [[ -n "$value" && ! "$value" =~ [^A-Za-z0-9_.,@%+=:/-] ]] || die "$name contains unsupported characters: $value"
}

release="${FEDORA_RELEASE:-stable}"
arch="${ARCH:-x86_64}"
user_name="${FEDORA_USB_USER:-fedora}"
hostname="${FEDORA_USB_HOSTNAME:-fedora-usb}"
timezone="${FEDORA_USB_TIMEZONE:-UTC}"
locale="${FEDORA_USB_LOCALE:-en_US.UTF-8}"
console_keymap="${FEDORA_USB_CONSOLE_KEYMAP:-us}"
xkb_layout="${FEDORA_USB_XKB_LAYOUT:-us}"
bootloader="${FEDORA_USB_BOOTLOADER:-grub}"
boot_timeout="${FEDORA_USB_BOOT_TIMEOUT:-3}"
image_size="${IMAGE_SIZE:-16G}"
image_name="${IMAGE_NAME:-fedora-usb.img}"
output_path="${OUTPUT_PATH:-$image_name}"
packages="${FEDORA_USB_PACKAGES:-}"
groups="${FEDORA_USB_GROUPS:-core}"
services="${FEDORA_USB_SERVICES:-}"
default_target="${FEDORA_USB_DEFAULT_TARGET:-multi-user.target}"
warnings="${FEDORA_USB_WARNINGS:-}"

[[ "$release" =~ ^(stable|rawhide|[0-9]{2,3})$ ]] || die "Fedora release must be stable, rawhide, or numeric"
[[ "$arch" == "x86_64" ]] || die "Only Fedora x86_64 is currently supported"
[[ "$user_name" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "Username must be lowercase letters/numbers/_/- and start with letter/_"
[[ "$hostname" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || die "Invalid hostname"
[[ "$bootloader" =~ ^(grub|systemd-boot)$ ]] || die "Unsupported Fedora bootloader: $bootloader"
[[ "$boot_timeout" =~ ^[0-9]+$ ]] || die "Boot timeout must be numeric"
safe_token Timezone "$timezone"
safe_token Locale "$locale"
safe_token Console-keymap "$console_keymap"
safe_token XKB-layout "$xkb_layout"
for pkg in $packages; do
  [[ "$pkg" =~ ^[A-Za-z0-9][A-Za-z0-9+_.-]*$ ]] || die "Invalid package name: $pkg"
done

log "Fedora USB plan"
log "  release: $release  arch: $arch  image: $output_path  size: $image_size"
log "  groups: ${groups:-none}"
log "  packages: $(wc -w <<<"$packages" | tr -d ' ') selected"
log "  services: ${services:-none}"
log "  target: $default_target"
if [[ -n "$warnings" ]]; then
  while IFS= read -r line; do [[ -n "$line" ]] && log "  warning: $line"; done <<<"$warnings"
fi
if [[ "$DRY_RUN" == "1" ]]; then
  log "Dry-run OK: Fedora configuration is valid."
  log "Package list: $packages"
  exit 0
fi

[[ "$(uname -s)" == "Linux" ]] || die "Fedora image build currently requires a Linux host or VM (dry-run works everywhere)."
need dnf
need parted
need mkfs.vfat
need mkfs.ext4
need losetup
need mount
need rsync
need grub2-install
need grub2-mkconfig

if [[ $EUID -ne 0 ]]; then
  die "Fedora image build requires root on Linux because it creates loop devices and filesystems. Re-run with sudo, or use --dry-run."
fi

workdir="${FEDORA_USB_WORKDIR:-.work/fedora-build}"
rootfs="$workdir/rootfs"
mkdir -p "$workdir"
rm -rf "$rootfs"
mkdir -p "$rootfs"
truncate -s "$image_size" "$output_path"
loop="$(losetup --find --show "$output_path")"
cleanup() {
  set +e
  mountpoint -q "$rootfs/boot/efi" && umount "$rootfs/boot/efi"
  mountpoint -q "$rootfs" && umount "$rootfs"
  losetup -d "$loop" >/dev/null 2>&1
}
trap cleanup EXIT
parted -s "$loop" mklabel gpt mkpart ESP fat32 1MiB 513MiB set 1 esp on mkpart root ext4 513MiB 100%
partprobe "$loop" || true
sleep 1
boot_part="${loop}p1"; root_part="${loop}p2"
[[ -e "$boot_part" ]] || boot_part="/dev/mapper/$(basename "$loop")p1"
[[ -e "$root_part" ]] || root_part="/dev/mapper/$(basename "$loop")p2"
mkfs.vfat -F32 "$boot_part"
mkfs.ext4 -F -L fedora-usb "$root_part"
mount "$root_part" "$rootfs"
mkdir -p "$rootfs/boot/efi"
mount "$boot_part" "$rootfs/boot/efi"
release_args=()
[[ "$release" != "stable" ]] && release_args=("--releasever=$release")
dnf -y --installroot="$rootfs" --forcearch="$arch" "${release_args[@]}" --setopt=install_weak_deps=False install $packages $(printf '@%s ' $groups)
echo "$hostname" > "$rootfs/etc/hostname"
ln -sf "../usr/share/zoneinfo/$timezone" "$rootfs/etc/localtime" || true
echo "LANG=$locale" > "$rootfs/etc/locale.conf"
echo "KEYMAP=$console_keymap" > "$rootfs/etc/vconsole.conf"
mkdir -p "$rootfs/etc/X11/xorg.conf.d"
printf 'Section "InputClass"\n Identifier "keyboard"\n MatchIsKeyboard "on"\n Option "XkbLayout" "%s"\nEndSection\n' "$xkb_layout" > "$rootfs/etc/X11/xorg.conf.d/00-keyboard.conf"
chroot "$rootfs" useradd -m -G wheel "$user_name"
if [[ -n "${FEDORA_USB_PASSWORD_FILE:-}" && -f "${FEDORA_USB_PASSWORD_FILE}" ]]; then
  printf '%s:%s\n' "$user_name" "$(cat "$FEDORA_USB_PASSWORD_FILE")" | chroot "$rootfs" chpasswd
fi
if [[ -n "${FEDORA_USB_ROOT_PASSWORD_FILE:-}" && -f "${FEDORA_USB_ROOT_PASSWORD_FILE}" ]]; then
  printf 'root:%s\n' "$(cat "$FEDORA_USB_ROOT_PASSWORD_FILE")" | chroot "$rootfs" chpasswd
fi
chroot "$rootfs" systemctl set-default "$default_target"
for svc in $services; do chroot "$rootfs" systemctl enable "$svc" || true; done
chroot "$rootfs" grub2-install --target=x86_64-efi --efi-directory=/boot/efi --removable --bootloader-id=FedoraUSB --recheck
chroot "$rootfs" grub2-mkconfig -o /boot/grub2/grub.cfg
sync
log "Image ready: $output_path"
