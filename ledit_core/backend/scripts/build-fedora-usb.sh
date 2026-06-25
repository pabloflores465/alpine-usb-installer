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
hostname="${FEDORA_USB_HOSTNAME:-ledit-fedora}"
timezone="${FEDORA_USB_TIMEZONE:-UTC}"
locale="${FEDORA_USB_LOCALE:-en_US.UTF-8}"
console_keymap="${FEDORA_USB_CONSOLE_KEYMAP:-us}"
xkb_layout="${FEDORA_USB_XKB_LAYOUT:-us}"
bootloader="${FEDORA_USB_BOOTLOADER:-grub}"
boot_timeout="${FEDORA_USB_BOOT_TIMEOUT:-3}"
image_size="${IMAGE_SIZE:-16G}"
image_name="${IMAGE_NAME:-ledit-fedora.img}"
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

# macOS cannot create Linux filesystems/loop devices natively. Re-exec inside a
# privileged Fedora container, mirroring the Alpine Docker builder path.
if [[ "$(uname -s)" == "Darwin" && "${FEDORA_USB_BUILD_IN_DOCKER:-0}" != "1" ]]; then
  need docker
  docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop and try again."

  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
  docker_image="${FEDORA_USB_DOCKER_IMAGE:-fedora:latest}"
  pass_env=(
    IMAGE_NAME OUTPUT_PATH IMAGE_SIZE ARCH LINUX_USB_DISTRO
    FEDORA_RELEASE FEDORA_USB_PROFILE FEDORA_USB_USER FEDORA_USB_PASSWORD_FILE FEDORA_USB_ROOT_PASSWORD_FILE
    FEDORA_USB_HOSTNAME FEDORA_USB_TIMEZONE FEDORA_USB_LOCALE FEDORA_USB_LANGUAGE
    FEDORA_USB_CONSOLE_KEYMAP FEDORA_USB_XKB_LAYOUT FEDORA_USB_XKB_VARIANT FEDORA_USB_XKB_MODEL
    FEDORA_USB_DESKTOP FEDORA_USB_TILING_WMS FEDORA_USB_DEFAULT_SESSION FEDORA_USB_DISPLAY_MANAGER
    FEDORA_USB_NETWORK FEDORA_USB_WIFI FEDORA_USB_BLUETOOTH FEDORA_USB_AUDIO FEDORA_USB_BROWSER
    FEDORA_USB_FIRMWARE FEDORA_USB_LEGACY_X11_DRIVERS FEDORA_USB_BOOTLOADER FEDORA_USB_KERNEL_FLAVOR
    FEDORA_USB_BOOT_TIMEOUT FEDORA_USB_SYSTEMD_BOOT_CONSOLE_MODE FEDORA_USB_AUTO_RESIZE
    FEDORA_USB_EXTRA_PACKAGES FEDORA_USB_PACKAGES FEDORA_USB_GROUPS FEDORA_USB_SERVICES
    FEDORA_USB_DEFAULT_TARGET FEDORA_USB_WARNINGS FEDORA_USB_WORKDIR
  )
  docker_env=(-e FEDORA_USB_BUILD_IN_DOCKER=1)
  docker_mounts=(-v "$PROJECT_ROOT:/work")
  docker_name_args=()
  docker_name="${FEDORA_USB_DOCKER_NAME:-${LEDIT_USB_DOCKER_NAME:-}}"
  if [[ -n "$docker_name" ]]; then
    if [[ "$docker_name" == *[!A-Za-z0-9_.-]* ]]; then echo "Invalid Docker container name: $docker_name" >&2; exit 1; fi
    docker_name_args=(--name "$docker_name")
  fi
  for name in "${pass_env[@]}"; do
    value="${!name-}"
    if [[ "$name" == "OUTPUT_PATH" && -n "$value" ]]; then
      mkdir -p "$(dirname "$value")"
      output_dir="$(cd "$(dirname "$value")" && pwd -P)"
      output_base="$(basename "$value")"
      docker_mounts+=(-v "$output_dir:/out")
      docker_env+=(-e "OUTPUT_PATH=/out/$output_base")
      continue
    fi
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$PROJECT_ROOT/"* ]]; then
      value="/work/${value#"$PROJECT_ROOT"/}"
    fi
    docker_env+=(-e "$name=$value")
  done

  log "Starting Docker Fedora build container ($docker_image)..."
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
    "${docker_env[@]}" \
    "${docker_mounts[@]}" \
    -w /work \
    "$docker_image" \
    bash -ceu '
      dnf -y install dnf-plugins-core parted dosfstools e2fsprogs util-linux util-linux-core \
        rsync grub2-tools grub2-tools-extra grub2-efi-x64 shim-x64 passwd policycoreutils kpartx >/dev/null
      chmod +x ledit_core/backend/scripts/build-fedora-usb.sh
      exec ledit_core/backend/scripts/build-fedora-usb.sh
    '
fi

[[ "$(uname -s)" == "Linux" ]] || die "Fedora image build currently requires a Linux host, VM, or Docker Desktop on macOS (dry-run works everywhere)."
need dnf
need parted
need mkfs.vfat
need mkfs.ext4
need losetup
need mount
need rsync
need grub2-install
need grub2-mkconfig

device_ready() {
  local path="$1" size
  [[ -b "$path" ]] || return 1
  size="$(blockdev --getsize64 "$path" 2>/dev/null || true)"
  [[ "$size" =~ ^[0-9]+$ && "$size" -gt 0 ]]
}

wait_for_device() {
  local path="$1"
  for _ in $(seq 1 30); do
    device_ready "$path" && return 0
    sleep 1
  done
  return 1
}

settle_loop_partitions() {
  local loopdev="$1"
  local direct_boot="${loopdev}p1"
  local direct_root="${loopdev}p2"
  local mapper_base="/dev/mapper/$(basename "$loopdev")"
  local mapper_boot="${mapper_base}p1"
  local mapper_root="${mapper_base}p2"

  if [[ "${FEDORA_USB_BUILD_IN_DOCKER:-0}" != "1" ]]; then
    partprobe "$loopdev" >/dev/null 2>&1 || true
  fi
  blockdev --rereadpt "$loopdev" >/dev/null 2>&1 || true
  partx -a "$loopdev" >/dev/null 2>&1 || partx -u "$loopdev" >/dev/null 2>&1 || true
  if wait_for_device "$direct_boot" && wait_for_device "$direct_root"; then
    boot_part="$direct_boot"
    root_part="$direct_root"
    return 0
  fi

  if command -v kpartx >/dev/null 2>&1; then
    kpartx -d "$loopdev" >/dev/null 2>&1 || true
    kpartx -avs "$loopdev" >/dev/null 2>&1 || true
    command -v dmsetup >/dev/null 2>&1 && dmsetup mknodes >/dev/null 2>&1 || true
    if wait_for_device "$mapper_boot" && wait_for_device "$mapper_root"; then
      boot_part="$mapper_boot"
      root_part="$mapper_root"
      return 0
    fi
  fi

  die "Kernel did not expose loop partitions for $loopdev. Try Docker Desktop restart, or build on a Linux VM."
}

mount_chroot_api() {
  mkdir -p "$rootfs/dev" "$rootfs/proc" "$rootfs/sys" "$rootfs/run"
  mountpoint -q "$rootfs/dev" || mount --rbind /dev "$rootfs/dev"
  mountpoint -q "$rootfs/proc" || mount -t proc proc "$rootfs/proc"
  mountpoint -q "$rootfs/sys" || mount --rbind /sys "$rootfs/sys" || true
  mountpoint -q "$rootfs/run" || mount --rbind /run "$rootfs/run" || true
}

if [[ $EUID -ne 0 ]]; then
  die "Fedora image build requires root on Linux because it creates loop devices and filesystems. Re-run with sudo, or use --dry-run."
fi

workdir="${FEDORA_USB_WORKDIR:-$PWD/.work/fedora-build}"
mkdir -p "$workdir"
workdir="$(cd "$workdir" && pwd -P)"
rootfs="$workdir/rootfs"
rm -rf "$rootfs"
mkdir -p "$rootfs"
if [[ "${FEDORA_USB_BUILD_IN_DOCKER:-0}" == "1" ]]; then
  [[ -e /dev/loop-control ]] || mknod /dev/loop-control c 10 237 || true
  for i in $(seq 0 15); do
    [[ -e "/dev/loop$i" ]] || mknod "/dev/loop$i" b 7 "$i" || true
  done
fi
truncate -s "$image_size" "$output_path"
parted -s "$output_path" mklabel gpt mkpart ESP fat32 1MiB 513MiB set 1 esp on mkpart root ext4 513MiB 100%
loop="$(losetup --partscan --find --show "$output_path")"
cleanup() {
  set +e
  for mp in "$rootfs/run" "$rootfs/sys" "$rootfs/proc" "$rootfs/dev" "$rootfs/boot/efi" "$rootfs"; do
    mountpoint -q "$mp" && umount -R "$mp" >/dev/null 2>&1
  done
  command -v kpartx >/dev/null 2>&1 && kpartx -d "$loop" >/dev/null 2>&1
  losetup -d "$loop" >/dev/null 2>&1
}
trap cleanup EXIT
boot_part=""
root_part=""
settle_loop_partitions "$loop"
log "Using partitions: boot=$boot_part root=$root_part"
mkfs.vfat -F32 "$boot_part"
mkfs.ext4 -F -L fedora-usb "$root_part"
mount "$root_part" "$rootfs"
mkdir -p "$rootfs/boot/efi"
mount "$boot_part" "$rootfs/boot/efi"
mount_chroot_api
mkdir -p "$rootfs/etc/default"
if ! grep -q '^GRUB_DISABLE_OS_PROBER=' "$rootfs/etc/default/grub" 2>/dev/null; then
  printf '%s\n' 'GRUB_DISABLE_OS_PROBER=true' >> "$rootfs/etc/default/grub"
fi
release_args=()
[[ "$release" != "stable" ]] && release_args=("--releasever=$release")
dnf_root_args=(-y --use-host-config --installroot="$rootfs" --forcearch="$arch")
log "Installing Fedora packages into installroot with host DNF repositories..."
SYSTEMD_OFFLINE=1 dnf "${dnf_root_args[@]}" "${release_args[@]}" --setopt=install_weak_deps=False install $packages $(printf '@%s ' $groups)
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
if ! grep -q '^GRUB_DISABLE_OS_PROBER=' "$rootfs/etc/default/grub" 2>/dev/null; then
  printf '%s\n' 'GRUB_DISABLE_OS_PROBER=true' >> "$rootfs/etc/default/grub"
fi
mount_chroot_api
chroot "$rootfs" grub2-install --target=x86_64-efi --efi-directory=/boot/efi --removable --bootloader-id=FedoraUSB --recheck --no-nvram --force
chroot "$rootfs" grub2-mkconfig -o /boot/grub2/grub.cfg
sync
log "Image ready: $output_path"
