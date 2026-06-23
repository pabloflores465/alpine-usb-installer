#!/usr/bin/env bash
# Experimental openSUSE image builder foundation. Uses zypper --root when run on Linux with required privileges/tools.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-ledit-opensuse.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
WORK_DIR="${WORK_DIR:-$PROJECT_ROOT/.work/opensuse}"
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 1; }; }
[[ "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ && "$IMAGE_NAME" != .*..* && "$IMAGE_NAME" != */* ]] || { echo "Invalid image name: $IMAGE_NAME" >&2; exit 1; }
if [ "$(uname -s)" = Darwin ] && [ "${OPENSUSE_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  need docker
  docker info >/dev/null 2>&1 || { echo "Docker is not running. Start Docker Desktop and try again." >&2; exit 1; }
  docker_env=(-e OPENSUSE_USB_BUILD_IN_DOCKER=1 -e IMAGE_NAME="$IMAGE_NAME" -e IMAGE_SIZE="$IMAGE_SIZE" -e WORK_DIR=/tmp/opensuse-work)
  docker_mounts=(-v "$PROJECT_ROOT:/work")
  if [ -n "$OUTPUT_PATH" ]; then
    mkdir -p "$(dirname "$OUTPUT_PATH")"
    output_dir="$(cd "$(dirname "$OUTPUT_PATH")" && pwd -P)"
    output_base="$(basename "$OUTPUT_PATH")"
    docker_mounts+=(-v "$output_dir:/out")
    docker_env+=(-e "OUTPUT_PATH=/out/$output_base")
  fi
  for name in OPENSUSE_RELEASE OPENSUSE_USB_PROFILE OPENSUSE_USB_USER OPENSUSE_USB_PASSWORD_FILE OPENSUSE_USB_ROOT_PASSWORD_FILE OPENSUSE_USB_HOSTNAME OPENSUSE_USB_TIMEZONE OPENSUSE_USB_LOCALE OPENSUSE_USB_LANGUAGE OPENSUSE_USB_CONSOLE_KEYMAP OPENSUSE_USB_XKB_LAYOUT OPENSUSE_USB_XKB_VARIANT OPENSUSE_USB_XKB_MODEL OPENSUSE_USB_DESKTOP OPENSUSE_USB_TILING_WMS OPENSUSE_USB_DEFAULT_SESSION OPENSUSE_USB_DISPLAY_MANAGER OPENSUSE_USB_NETWORK OPENSUSE_USB_WIFI OPENSUSE_USB_BLUETOOTH OPENSUSE_USB_AUDIO OPENSUSE_USB_BROWSER OPENSUSE_USB_FIRMWARE OPENSUSE_USB_LEGACY_X11_DRIVERS OPENSUSE_USB_BOOTLOADER OPENSUSE_USB_KERNEL_FLAVOR OPENSUSE_USB_BOOT_TIMEOUT OPENSUSE_USB_SYSTEMD_BOOT_CONSOLE_MODE OPENSUSE_USB_AUTO_RESIZE OPENSUSE_USB_EXTRA_PACKAGES; do
    value="${!name-}"
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$PROJECT_ROOT/"* ]]; then value="/work/${value#"$PROJECT_ROOT"/}"; fi
    docker_env+=(-e "$name=$value")
  done
  docker_name_args=()
  if [ -n "${OPENSUSE_USB_DOCKER_NAME:-}" ]; then
    if [[ "$OPENSUSE_USB_DOCKER_NAME" == *[!A-Za-z0-9_.-]* ]]; then echo "Invalid Docker container name: $OPENSUSE_USB_DOCKER_NAME" >&2; exit 1; fi
    docker_name_args=(--name "$OPENSUSE_USB_DOCKER_NAME")
  fi
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged "${docker_env[@]}" "${docker_mounts[@]}" -w /work opensuse/tumbleweed bash -ceu '
    zypper --non-interactive refresh >/dev/null
    zypper --non-interactive install -y bash gawk python3 qemu-tools parted e2fsprogs dosfstools util-linux util-linux-systemd grub2 grub2-x86_64-efi >/dev/null
    chmod +x backend/scripts/build-opensuse-usb.sh backend/scripts/configure-opensuse-usb.sh
    exec backend/scripts/build-opensuse-usb.sh
  '
fi
if [ "$(uname -s)" != Linux ]; then echo "openSUSE builds require Linux with zypper/loop tools; use --dry-run on this host." >&2; exit 1; fi
need zypper; need qemu-img; need parted; need mkfs.ext4; need mkfs.fat; need losetup; need blkid; need findmnt; need chroot
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }
read_secret() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var:-}"; eval "direct_value=\${$value_var:-}"
  if [ -n "$file_value" ]; then [ -f "$file_value" ] || { echo "Secret file not found: $file_value" >&2; exit 1; }; cat "$file_value"
  elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"
  else printf '%s' "$default_value"; fi
}

mkdir -p "$WORK_DIR"
# Validate the plan up front (also surfaces a human-readable summary).
OPENSUSE_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-opensuse-usb.sh" >/dev/null
packages="${OPENSUSE_USB_PACKAGE_PLAN:-}"
[ -n "$packages" ] || packages="$({ OPENSUSE_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-opensuse-usb.sh" | sed -n 's/^Packages://p'; })"

RELEASE="$(lower "${OPENSUSE_RELEASE:-tumbleweed}")"
BOOTLOADER="$(lower "${OPENSUSE_USB_BOOTLOADER:-grub}")"
case "$BOOTLOADER" in grub|systemd-boot|systemdboot) BOOTLOADER="${BOOTLOADER/systemdboot/systemd-boot}" ;; *) echo "Unsupported bootloader: $BOOTLOADER" >&2; exit 1 ;; esac
DM="$(lower "${OPENSUSE_USB_DISPLAY_MANAGER:-auto}")"
DESKTOP="$(lower "${OPENSUSE_USB_DESKTOP:-xfce}")"
TILING_WMS="$(printf '%s' "${OPENSUSE_USB_TILING_WMS:-}" | tr ',;:' '   ')"
[ "$DM" = auto ] && case "$DESKTOP" in gnome) DM=gdm ;; plasma|lxqt) DM=sddm ;; xfce|mate) DM=lightdm ;; none) [ -n "$TILING_WMS" ] && DM=greetd || DM=none ;; esac
NETWORK_BACKEND="$(lower "${OPENSUSE_USB_NETWORK:-networkmanager}")"

USER_NAME="${OPENSUSE_USB_USER:-linux}"
USER_PASSWORD="$(read_secret OPENSUSE_USB_PASSWORD_FILE OPENSUSE_USB_PASSWORD linux)"
ROOT_PASSWORD="$(read_secret OPENSUSE_USB_ROOT_PASSWORD_FILE OPENSUSE_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${OPENSUSE_USB_HOSTNAME:-ledit-opensuse}"
TIMEZONE="${OPENSUSE_USB_TIMEZONE:-UTC}"
LOCALE="${OPENSUSE_USB_LOCALE:-en_US.UTF-8}"
CONSOLE_KEYMAP="${OPENSUSE_USB_CONSOLE_KEYMAP:-us}"
BOOT_TIMEOUT="${OPENSUSE_USB_BOOT_TIMEOUT:-3}"
AUTO_RESIZE="${OPENSUSE_USB_AUTO_RESIZE:-1}"

repo_url="https://download.opensuse.org/tumbleweed/repo/oss"
case "$RELEASE" in leap-*) repo_url="https://download.opensuse.org/${RELEASE/-/\/}/repo/oss" ;; esac

image="$WORK_DIR/$IMAGE_NAME"
root="$WORK_DIR/root"
rm -rf "$root" "$image"
mkdir -p "$root"

# --- Partition + format the raw image (GPT: ESP + ext4 root) ---
qemu-img create -f raw "$image" "$IMAGE_SIZE"
echo "Created raw image: $image"
parted -s "$image" mklabel gpt unit MiB mkpart ESP fat32 1 513 set 1 esp on mkpart root ext4 513 100%
echo "Partitioned image: GPT ESP(512MiB) + root(ext4)"
# Container-safe loop setup: attach each partition by byte offset (losetup -P
# partition nodes are not always created without udev inside Docker).
read -r esp_off esp_sz root_off root_sz <<PARTS
$(parted -s "$image" unit B print | awk '/^ 1 /{gsub(/B$/,"",$2); gsub(/B$/,"",$4); e2=$2; e4=$4} /^ 2 /{gsub(/B$/,"",$2); gsub(/B$/,"",$4); r2=$2; r4=$4} END{print e2, e4, r2, r4}')
PARTS
[ -n "$root_off" ] || { echo "Could not parse partition offsets" >&2; exit 1; }
esp_dev="$(losetup -f -o "$esp_off" --sizelimit "$esp_sz" --show "$image")"
root_dev="$(losetup -f -o "$root_off" --sizelimit "$root_sz" --show "$image")"
mkfs.fat -F32 -n ESP "$esp_dev"
mkfs.ext4 -F -L root "$root_dev"
echo "Formatted ESP (FAT32) and root (ext4)"

root_uuid="$(blkid -s UUID -o value "$root_dev")"
esp_uuid="$(blkid -s UUID -o value "$esp_dev")"

mount "$root_dev" "$root"
mkdir -p "$root/boot/efi"
mount "$esp_dev" "$root/boot/efi"

cleanup() {
  set +e
  for m in dev/pts dev sys proc run boot/efi; do
    mountpoint -q "$root/$m" 2>/dev/null && umount "$root/$m" 2>/dev/null
  done
  mountpoint -q "$root" 2>/dev/null && umount "$root" 2>/dev/null
  [ -n "${esp_dev:-}" ] && losetup -d "$esp_dev" 2>/dev/null || true
  [ -n "${root_dev:-}" ] && losetup -d "$root_dev" 2>/dev/null || true
}
trap cleanup EXIT

# --- Install the openSUSE package root directly into the mounted root ---
echo "Installing openSUSE packages into $root (this takes a while)..."
zypper --non-interactive --root "$root" ar -f "$repo_url" oss
zypper --non-interactive --root "$root" --gpg-auto-import-keys refresh
# shellcheck disable=SC2086
zypper --non-interactive --root "$root" install --no-recommends $packages

# --- Base system configuration (no chroot needed) ---
echo "$HOSTNAME" > "$root/etc/hostname"
cat > "$root/etc/hosts" <<HOSTS
127.0.0.1 localhost $HOSTNAME
::1       localhost $HOSTNAME
HOSTS
ln -sf "/usr/share/zoneinfo/$TIMEZONE" "$root/etc/localtime"
printf 'LANG=%s\n' "$LOCALE" > "$root/etc/locale.conf"
printf 'KEYMAP=%s\n' "$CONSOLE_KEYMAP" > "$root/etc/vconsole.conf"
: > "$root/etc/machine-id"   # let systemd generate a stable id on first boot

# --- /etc/fstab ---
cat > "$root/etc/fstab" <<FSTAB
UUID=$root_uuid  /          ext4  defaults,rw,relatime  0 1
UUID=$esp_uuid   /boot/efi  vfat  umask=0077            0 2
tmpfs            /tmp       tmpfs defaults              0 0
tmpfs            /run       tmpfs defaults              0 0
FSTAB

# --- Bind-mount the kernel APIs we need for dracut/grub/user setup ---
mount --bind /proc "$root/proc"
mount --bind /sys "$root/sys"
mount --bind /dev "$root/dev"
mkdir -p "$root/dev/pts"; mount --bind /dev/pts "$root/dev/pts" 2>/dev/null || true
mount -t tmpfs tmpfs "$root/run"

# --- Kernel boot symlinks + initrd ---
kver="$(find "$root/lib/modules" -maxdepth 1 -mindepth 1 -type d -printf "%f\n" 2>/dev/null | sort | head -n1)"
if [ -z "$kver" ]; then echo "No kernel installed under /lib/modules" >&2; exit 1; fi
ln -sf "vmlinuz-$kver" "$root/boot/vmlinuz"
echo "Regenerating initrd for kernel $kver..."
chroot "$root" dracut --force "/boot/initrd-$kver" "$kver"
ln -sf "initrd-$kver" "$root/boot/initrd"

# --- Bootloader ---
case "$BOOTLOADER" in
  grub)
    cat > "$root/etc/default/grub" <<GRUB
GRUB_TIMEOUT=$BOOT_TIMEOUT
GRUB_DISTRIBUTOR="openSUSE USB"
GRUB_DEFAULT=saved
GRUB_DISABLE_SUBMENU=true
GRUB_DISABLE_OS_PROBER=true
GRUB_TERMINAL_OUTPUT=console
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash=silent"
GRUB_CMDLINE_LINUX=""
GRUB
    echo "Installing GRUB2 EFI (removable) and generating config..."
    chroot "$root" grub2-install --target=x86_64-efi --efi-directory=/boot/efi --boot-directory=/boot/grub2 --removable --no-nvram
    chroot "$root" grub2-mkconfig -o /boot/grub2/grub.cfg
    ;;
  systemd-boot)
    echo "Installing systemd-boot and writing boot entries..."
    mkdir -p "$root/boot/efi/loader/entries"
    cp "$root/boot/vmlinuz-$kver" "$root/boot/efi/vmlinuz-$kver"
    cp "$root/boot/initrd-$kver" "$root/boot/efi/initrd-$kver"
    chroot "$root" bootctl --esp-path=/boot/efi install
    cat > "$root/boot/efi/loader/loader.conf" <<LOADER
default opensuse
timeout $BOOT_TIMEOUT
LOADER
    cat > "$root/boot/efi/loader/entries/opensuse.conf" <<ENTRY
title openSUSE USB ($kver)
linux /vmlinuz-$kver
initrd /initrd-$kver
options root=UUID=$root_uuid rw rootfstype=ext4 quiet
ENTRY
    ;;
esac

# --- User, passwords and sudo ---
echo "Creating user $USER_NAME and setting passwords..."
chroot "$root" groupadd -f wheel 2>/dev/null || true
chroot "$root" useradd -m -G wheel,audio,video,users -s /bin/bash "$USER_NAME"
printf '%s:%s\n' "$USER_NAME" "$USER_PASSWORD" | chroot "$root" chpasswd
printf 'root:%s\n' "$ROOT_PASSWORD" | chroot "$root" chpasswd
mkdir -p "$root/etc/sudoers.d"
printf '%%wheel ALL=(ALL) NOPASSWD: ALL\n' > "$root/etc/sudoers.d/90-opensuse-usb"
chmod 0440 "$root/etc/sudoers.d/90-opensuse-usb"

# --- Enable services + default target ---
echo "Enabling system services..."
[ "$NETWORK_BACKEND" = networkmanager ] && chroot "$root" systemctl enable NetworkManager
is_enabled "${OPENSUSE_USB_BLUETOOTH:-1}" && chroot "$root" systemctl enable bluetooth
case "$DM" in
  lightdm|sddm|gdm|lxdm|greetd)
    # openSUSE can preseed display-manager.service -> display-manager-legacy.service.
    # Replace that alias with the selected display manager instead of failing.
    rm -f "$root/etc/systemd/system/display-manager.service"
    chroot "$root" systemctl enable --force "$DM"
    ;;
esac
if [ "$DM" = none ]; then
  chroot "$root" systemctl set-default multi-user.target
else
  chroot "$root" systemctl set-default graphical.target
fi

# --- First-boot auto-grow of the root partition ---
if is_enabled "$AUTO_RESIZE"; then
  cat > "$root/usr/local/sbin/opensuse-usb-grow-root.sh" <<'GROW'
#!/bin/bash
set -e
root_src="$(findmnt -nro SOURCE /)"
mapfile -t info < <(lsblk -no PKNAME,PARTN,TYPE "$root_src" 2>/dev/null | awk '$3=="part"{print $1; print $2; exit}')
[ "${#info[@]}" -eq 2 ] || { echo "opensuse-usb-grow: could not determine parent disk"; exit 0; }
pkname="${info[0]}"; partn="${info[1]}"
growpart "/dev/$pkname" "$partn" || true
resize2fs "$root_src" || true
touch /etc/opensuse-usb-grow-done
systemctl disable opensuse-usb-grow-root.service
GROW
  chmod 0755 "$root/usr/local/sbin/opensuse-usb-grow-root.sh"
  cat > "$root/etc/systemd/system/opensuse-usb-grow-root.service" <<SVC
[Unit]
Description=Grow root filesystem on first boot
ConditionPathExists=!/etc/opensuse-usb-grow-done
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/opensuse-usb-grow-root.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
SVC
  chroot "$root" systemctl enable opensuse-usb-grow-root.service
fi

# --- Tear down mounts and detach the loop device ---
umount "$root/proc" 2>/dev/null || true
umount "$root/dev/pts" 2>/dev/null || true
umount "$root/dev" 2>/dev/null || true
umount "$root/sys" 2>/dev/null || true
umount "$root/run" 2>/dev/null || true
umount "$root/boot/efi" 2>/dev/null || true
sync
umount "$root" 2>/dev/null || true
losetup -d "$esp_dev" 2>/dev/null || true
losetup -d "$root_dev" 2>/dev/null || true
trap - EXIT

if [ -n "$OUTPUT_PATH" ]; then
  mkdir -p "$(dirname "$OUTPUT_PATH")"
  mv "$image" "$OUTPUT_PATH"
  echo "Image ready: $OUTPUT_PATH"
else
  mv "$image" "$PROJECT_ROOT/$IMAGE_NAME"
  echo "Image ready: $PROJECT_ROOT/$IMAGE_NAME"
fi
