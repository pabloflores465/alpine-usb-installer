#!/usr/bin/env bash
# Build a configurable, installed Slackware Linux USB image.
#
# Slackware has no debootstrap/pacstrap equivalent with dependency resolution, so
# we bootstrap Slackware's own `installpkg` (from the pkgtools package) and
# install whole package series (the authentic Slackware install method) plus the
# user's selected extra packages into a rootfs. The rootfs is then packed into a
# GPT image with an ext4 root + FAT32 ESP and a standalone GRUB EFI bootloader.
set -euo pipefail

log() { printf '[slackware-build] %s\n' "$*"; }
fail() { printf '[slackware-build] ERROR: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Required tool not found: $1"; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }

shell_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }

read_secret() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var-}"; eval "direct_value=\${$value_var-}"
  if [ -n "$file_value" ]; then [ -f "$file_value" ] || fail "Secret file not found: $file_value"; cat "$file_value"
  elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"
  else printf '%s' "$default_value"; fi
}

release_path() {
  case "$1" in
    stable) printf 'slackware64-15.0' ;;
    current) printf 'slackware64-current' ;;
    [0-9]*.[0-9]*) printf 'slackware64-%s' "$1" ;;
    *) fail "Unsupported Slackware release: $1" ;;
  esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-ledit-slackware.img}"
OUTPUT_PATH="${OUTPUT_PATH:-}"
IMAGE_SIZE="${IMAGE_SIZE:-16G}"
ARCH_VALUE="${ARCH:-x86_64}"
WORK_DIR="${WORK_DIR:-$PROJECT_ROOT/.work}"
PKG_CACHE_DIR="${SLACKWARE_PKG_CACHE_DIR:-$WORK_DIR/slackware-pkgs}"
BUILD_DIR="${SLACKWARE_BUILD_DIR:-/var/tmp/slackware-usb-build-$$}"
BUILDER_BASE_IMAGE="alpine:3.22@sha256:310c62b5e7ca5b08167e4384c68db0fd2905dd9c7493756d356e893909057601"
DOCKER_IMAGE="${SLACKWARE_USB_DOCKER_IMAGE:-$BUILDER_BASE_IMAGE}"
BOOTLOADER="$(lower "${LEDIT_USB_BOOTLOADER:-grub}")"
[ "$BOOTLOADER" = "systemdboot" ] && BOOTLOADER="systemd-boot"

case "$ARCH_VALUE" in x86_64|amd64) ;; *) fail "Slackware installed image builder currently supports x86_64/amd64 only (got: $ARCH_VALUE)" ;; esac
case "$BOOTLOADER" in
  grub) ;;
  systemd-boot|elilo|syslinux) fail "Slackware installed image builder currently supports GRUB only; choose --bootloader grub" ;;
  *) fail "Unsupported bootloader: $BOOTLOADER" ;;
esac
if [[ -z "$IMAGE_NAME" || "$IMAGE_NAME" == *"/"* || "$IMAGE_NAME" == *".."* || "$IMAGE_NAME" == -* || ! "$IMAGE_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  fail "Invalid image name: $IMAGE_NAME"
fi
if [ -n "$OUTPUT_PATH" ]; then case "$OUTPUT_PATH" in /*) ;; *) fail "OUTPUT_PATH must be absolute: $OUTPUT_PATH" ;; esac; fi

# macOS / opt-in Docker path: run the whole builder inside a privileged Linux
# container with the tools needed to bootstrap pkgtools and assemble the image.
if { [ "$(uname -s)" = "Darwin" ] || is_enabled "${SLACKWARE_USB_FORCE_DOCKER:-0}"; } && [ "${SLACKWARE_USB_BUILD_IN_DOCKER:-0}" != "1" ]; then
  if ! command -v docker >/dev/null 2>&1; then fail "Docker not found. Install Docker Desktop and try again."; fi
  if ! docker info >/dev/null 2>&1; then fail "Docker is not running. Start Docker Desktop and try again."; fi
  pass_env=(
    IMAGE_NAME OUTPUT_PATH IMAGE_SIZE ARCH
    LEDIT_USB_USER LEDIT_USB_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_HOSTNAME
    LEDIT_USB_TIMEZONE LEDIT_USB_LOCALE LEDIT_USB_LANGUAGE LEDIT_USB_CONSOLE_KEYMAP
    LEDIT_USB_XKB_LAYOUT LEDIT_USB_XKB_VARIANT LEDIT_USB_XKB_MODEL
    LEDIT_USB_DESKTOP LEDIT_USB_TILING_WMS LEDIT_USB_DEFAULT_SESSION LEDIT_USB_DISPLAY_MANAGER
    LEDIT_USB_NETWORK LEDIT_USB_WIFI LEDIT_USB_BLUETOOTH LEDIT_USB_AUDIO LEDIT_USB_BROWSER
    LEDIT_USB_FIRMWARE LEDIT_USB_LEGACY_X11_DRIVERS LEDIT_USB_BOOTLOADER LEDIT_USB_KERNEL_FLAVOR
    LEDIT_USB_BOOT_TIMEOUT LEDIT_USB_AUTO_RESIZE LEDIT_USB_EXTRA_PACKAGES LEDIT_USB_PROFILE
    SLACKWARE_RELEASE SLACKWARE_MIRROR_BASE_URL SLACKWARE_PKG_CACHE_DIR SLACKWARE_BUILD_DIR
  )
  docker_env=(-e SLACKWARE_USB_BUILD_IN_DOCKER=1)
  docker_mounts=(-v "$PROJECT_ROOT:/work")
  docker_name_args=()
  [ -n "${SLACKWARE_USB_DOCKER_NAME:-}" ] && docker_name_args=(--name "$SLACKWARE_USB_DOCKER_NAME")
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
    if [[ "$name" == *_FILE && -n "$value" && "$value" == "$PROJECT_ROOT/"* ]]; then value="/work/${value#"$PROJECT_ROOT"/}"; fi
    if [ "$name" = "SLACKWARE_PKG_CACHE_DIR" ] && [ -n "$value" ] && [[ "$value" == "$PROJECT_ROOT/"* ]]; then value="/work/${value#"$PROJECT_ROOT"/}"; fi
    docker_env+=(-e "$name=$value")
  done
  log "Starting Slackware build container"
  exec docker run --rm "${docker_name_args[@]}" --platform linux/amd64 --privileged \
    "${docker_env[@]}" "${docker_mounts[@]}" -w /work "$DOCKER_IMAGE" \
    sh -ceu '
      apk add --no-cache bash curl tar xz zstd gzip bzip2 gawk coreutils findutils grep sed file \
        parted dosfstools e2fsprogs util-linux grub grub-efi mtools shadow cpio python3 >/dev/null
      chmod +x backend/scripts/build-slackware-usb.sh backend/scripts/configure-slackware-usb.sh
      exec backend/scripts/build-slackware-usb.sh
    '
fi

need awk; need curl; need tar; need parted; need truncate; need mkfs.vfat; need mkfs.ext4
need mmd; need mcopy; need grub-mkstandalone; need uuidgen; need dd; need chroot; need mount
[ "$(id -u)" = "0" ] || fail "Slackware installed image build needs root for chroot/loop mounts. On macOS this happens through Docker; on Linux run as root or set SLACKWARE_USB_FORCE_DOCKER=1."
if [ "${SLACKWARE_USB_BUILD_IN_DOCKER:-0}" = "1" ]; then
  [ -e /dev/loop-control ] || mknod /dev/loop-control c 10 237 2>/dev/null || true
  for i in $(seq 0 15); do [ -e "/dev/loop$i" ] || mknod "/dev/loop$i" b 7 "$i" 2>/dev/null || true; done
fi

OUTPUT=${OUTPUT_PATH:-$PROJECT_ROOT/$IMAGE_NAME}
RELEASE=${SLACKWARE_RELEASE:-stable}
TREE=$(release_path "$RELEASE")
MIRROR=${SLACKWARE_MIRROR_BASE_URL:-https://mirrors.slackware.com/slackware/$TREE}
HOSTNAME_VAL="${LEDIT_USB_HOSTNAME:-ledit-slackware}"
USER_NAME="${LEDIT_USB_USER:-slackware}"
USER_PASSWORD="$(read_secret LEDIT_USB_PASSWORD_FILE LEDIT_USB_PASSWORD slackware)"
ROOT_PASSWORD="$(read_secret LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD "$USER_PASSWORD")"
TIMEZONE="${LEDIT_USB_TIMEZONE:-UTC}"
LOCALE="${LEDIT_USB_LOCALE:-en_US.UTF-8}"
CONSOLE_KEYMAP="${LEDIT_USB_CONSOLE_KEYMAP:-us}"
BOOT_TIMEOUT="${LEDIT_USB_BOOT_TIMEOUT:-3}"
KERNEL_FLAVOR="$(lower "${LEDIT_USB_KERNEL_FLAVOR:-generic}")"
DESKTOP="$(lower "${LEDIT_USB_DESKTOP:-xfce}")"
DISPLAY_MANAGER="$(lower "${LEDIT_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${LEDIT_USB_NETWORK:-networkmanager}")"
TILING_WMS="${LEDIT_USB_TILING_WMS:-}"
FIRMWARE="$(lower "${LEDIT_USB_FIRMWARE:-full}")"
AUTO_RESIZE="${LEDIT_USB_AUTO_RESIZE:-1}"

mkdir -p "$WORK_DIR" "$PKG_CACHE_DIR" "$(dirname "$OUTPUT")"
chmod 700 "$WORK_DIR" 2>/dev/null || true

log "Validating Slackware build plan"
LEDIT_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-slackware-usb.sh" >/dev/null

# --- Determine which package series to install (authentic Slackware method) ---
SERIES="a ap l"
[ "$NETWORK_BACKEND" = "networkmanager" ] && SERIES="$SERIES n"
needs_x=no
case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt) needs_x=yes ;; esac
[ -n "$TILING_WMS" ] && needs_x=yes
case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm|greetd) needs_x=yes ;; esac
[ "$needs_x" = yes ] && SERIES="$SERIES x xap"
case "$DESKTOP" in xfce) SERIES="$SERIES xfce" ;; plasma) SERIES="$SERIES kde" ;; esac

# --- Fetch PACKAGES.TXT and build a base-name -> "location/name" map ---
PACKAGES_TXT="$PKG_CACHE_DIR/PACKAGES.TXT"
log "Fetching Slackware PACKAGES.TXT from $MIRROR"
curl -fsSL --retry 3 "$MIRROR/PACKAGES.TXT" -o "$PACKAGES_TXT"
MAP="$PKG_CACHE_DIR/name-map.tsv"
awk '
  /^PACKAGE NAME:/ { name=$3; next }
  /^PACKAGE LOCATION:/ {
    loc=$3; full=name; sub(/\.(txz|tar\.zst|tgz|tbz)$/, "", full);
    n=split(full, a, "-"); base=a[1]; for (i=2;i<=n-3;i++) base=base"-"a[i];
    print base "\t" loc "/" name; next
  }
' "$PACKAGES_TXT" > "$MAP"
log "Indexed $(wc -l < "$MAP") Slackware packages"

resolve_pkg() { awk -F'\t' -v b="$1" '$1==b{print $2; exit}' "$MAP"; }

in_series() { case " $SERIES " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

download_pkg() {
  # $1 = relative path like ./slackware64/a/pkg-1-x86_64-1.txz
  rel="$1"; rel_no_dot="${rel#./}"
  cache="$PKG_CACHE_DIR/$(basename "$rel")"
  if [ -s "$cache" ]; then echo "$cache"; return 0; fi
  curl -fsSL --retry 3 "$MIRROR/$rel_no_dot" -o "$cache"
  echo "$cache"
}

# Resolve the pkgtools package now so we can bootstrap `installpkg` after the
# build directory is (re)created below.
log "Locating Slackware pkgtools"
pkgtools_path=$(resolve_pkg pkgtools)
[ -n "$pkgtools_path" ] || fail "pkgtools not found in PACKAGES.TXT"
pkgtools_cache=$(download_pkg "$pkgtools_path")

ROOTFS="$BUILD_DIR/rootfs"
PT_DIR="$BUILD_DIR/pkgtools"
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
cleanup() {
  cleanup_chroot_mounts
  [ "${SLACKWARE_KEEP_BUILD_DIR:-0}" = "1" ] || rm -rf "$BUILD_DIR"
}
trap cleanup EXIT INT TERM

rm -rf "$BUILD_DIR"
mkdir -p "$ROOTFS" "$PT_DIR"
log "Bootstrapping Slackware pkgtools (installpkg)"
tar -xf "$pkgtools_cache" -C "$PT_DIR"
export PATH="$PT_DIR/sbin:$PATH"
command -v installpkg >/dev/null 2>&1 || fail "installpkg not available after pkgtools bootstrap"

# --- Install whole series (dependency-complete Slackware install) ---
log "Installing Slackware series: $SERIES"
installed_any=0
current_series=""
while IFS= read -r line; do
  base=$(printf '%s' "$line" | cut -f1)
  path=$(printf '%s' "$line" | cut -f2)
  series_dir=$(printf '%s' "$path" | sed 's#^\./slackware64/##; s#/.*##')
  in_series "$series_dir" || continue
  if [ "$series_dir" != "$current_series" ]; then
    current_series="$series_dir"
    log "  series $current_series: installing (installed so far: $installed_any)"
  fi
  cache=$(download_pkg "$path") || { log "skip (download failed): $base"; continue; }
  installpkg --root "$ROOTFS" "$cache" >/dev/null 2>&1 || log "skip (install failed): $base"
  installed_any=$((installed_any+1))
  if [ $((installed_any % 25)) -eq 0 ]; then
    log "  progress: $installed_any packages installed (current series: $current_series)"
  fi
done < "$MAP"
log "Installed $installed_any Slackware packages"
[ "$installed_any" -gt 0 ] || fail "No Slackware packages were installed"

# Honor firmware selection: drop the large kernel-firmware blob when not wanted.
if [ "$FIRMWARE" != "full" ]; then
  removepkg --root "$ROOTFS" kernel-firmware >/dev/null 2>&1 || true
fi

# --- Finalize glibc installation ---
# Slackware's glibc doinst.sh swaps libraries "on the fly" on a running glibc
# system using a lib*/incoming/ staging dir and *.incoming copies, gated on a
# working host /sbin/ldconfig. When installing into a foreign rootfs from a
# non-glibc host (e.g. an Alpine/musl builder container) that gate fails mid-way
# and the dynamic loader symlink is left dangling at "ld-*.so.incoming", which
# breaks every later chroot. Promote the incoming libraries and repoint any
# *.incoming symlinks before we touch the rootfs with chroot.
finalize_glibc() {
  root="$1"
  for libdir in lib64 lib; do
    [ -d "$root/$libdir/incoming" ] && mv "$root/$libdir/incoming"/* "$root/$libdir/" 2>/dev/null || true
    rmdir "$root/$libdir/incoming" 2>/dev/null || true
    for link in "$root/$libdir"/*; do
      [ -L "$link" ] || continue
      target=$(readlink "$link") || continue
      case "$target" in
        *.incoming)
          real=$(basename "$target" .incoming)
          [ -e "$root/$libdir/$real" ] && ln -sf "$real" "$link"
          ;;
      esac
    done
  done
}
log "Finalizing glibc loader in rootfs"
finalize_glibc "$ROOTFS"

# --- Install the user's selected extra packages (best-effort) ---
log "Installing selected extra packages"
while IFS= read -r pkg; do
  [ -n "$pkg" ] || continue
  path=$(resolve_pkg "$pkg")
  [ -n "$path" ] || { log "extra not in official tree, skip: $pkg"; continue; }
  cache=$(download_pkg "$path") || { log "extra download failed, skip: $pkg"; continue; }
  installpkg --root "$ROOTFS" "$cache" >/dev/null 2>&1 || log "extra install failed, skip: $pkg"
done <<EXTRA
$( { LEDIT_USB_DRY_RUN=1 "$SCRIPT_DIR/configure-slackware-usb.sh" | sed -n '/^Packages:/,$p' | sed '1d'; } | tr -d ' ' )
EXTRA

# Mount the kernel APIs once and rebuild the loader cache before any chroot
# command (useradd/chpasswd/mkinitrd). ldconfig repairs any remaining glibc
# symlinks so later chroot binaries find libc.
log "Mounting chroot API filesystems"
mount -t proc proc "$ROOTFS/proc"
mount --rbind /sys "$ROOTFS/sys"
mount --make-rslave "$ROOTFS/sys" >/dev/null 2>&1 || true
mount --rbind /dev "$ROOTFS/dev"
mount --make-rslave "$ROOTFS/dev" >/dev/null 2>&1 || true
CHROOT_MOUNTED=1
chroot "$ROOTFS" /sbin/ldconfig 2>/dev/null || true

# --- Base system configuration ---
echo "$HOSTNAME_VAL" > "$ROOTFS/etc/HOSTNAME"
cat > "$ROOTFS/etc/hosts" <<HOSTS
127.0.0.1 localhost $HOSTNAME_VAL
::1       localhost $HOSTNAME_VAL
HOSTS
ln -sf "/usr/share/zoneinfo/$TIMEZONE" "$ROOTFS/etc/localtime" 2>/dev/null || true
mkdir -p "$ROOTFS/etc/profile.d"
cat > "$ROOTFS/etc/profile.d/lang.sh" <<LANG
export LANG=$LOCALE
export LC_COLLATE=C
LANG
printf 'KEYMAP=%s\n' "$CONSOLE_KEYMAP" > "$ROOTFS/etc/vconsole.conf"
: > "$ROOTFS/etc/machine-id"

# --- User, passwords and sudo ---
log "Creating user $USER_NAME and setting passwords"
chroot "$ROOTFS" useradd -m -G wheel,audio,video,users -s /bin/bash "$USER_NAME" 2>/dev/null || \
  chroot "$ROOTFS" useradd -m -G wheel -s /bin/bash "$USER_NAME" 2>/dev/null || true
printf '%s:%s\n' "$USER_NAME" "$USER_PASSWORD" | chroot "$ROOTFS" chpasswd
printf 'root:%s\n' "$ROOT_PASSWORD" | chroot "$ROOTFS" chpasswd
if [ -d "$ROOTFS/etc/sudoers.d" ]; then
  printf '%%wheel ALL=(ALL) NOPASSWD: ALL\n' > "$ROOTFS/etc/sudoers.d/90-slackware-usb"
  chmod 0440 "$ROOTFS/etc/sudoers.d/90-slackware-usb"
fi

# --- Slackware BSD-init service enablement ---
log "Enabling Slackware services"
[ "$NETWORK_BACKEND" = "networkmanager" ] && [ -f "$ROOTFS/etc/rc.d/rc.networkmanager" ] && chmod 0755 "$ROOTFS/etc/rc.d/rc.networkmanager" 2>/dev/null || true
if is_enabled "${LEDIT_USB_BLUETOOTH:-1}" && [ -f "$ROOTFS/etc/rc.d/rc.bluetooth" ]; then
  chmod 0755 "$ROOTFS/etc/rc.d/rc.bluetooth" 2>/dev/null || true
fi
# Default runlevel: 4 (graphical) if a display manager is present, else 3 (multi-user).
have_dm=no
case "$DISPLAY_MANAGER" in
  lightdm|sddm|gdm|lxdm|greetd) [ -f "$ROOTFS/etc/rc.d/rc.$DISPLAY_MANAGER" ] && have_dm=yes ;;
esac
if [ "$have_dm" = yes ]; then
  chmod 0755 "$ROOTFS/etc/rc.d/rc.$DISPLAY_MANAGER" 2>/dev/null || true
  sed -i 's/^id:3:initdefault:/id:4:initdefault:/' "$ROOTFS/etc/inittab" 2>/dev/null || true
fi

# --- First-boot auto-grow of the root filesystem ---
if is_enabled "$AUTO_RESIZE"; then
  cat > "$ROOTFS/etc/rc.d/rc.grow-root" <<'GROW'
#!/bin/sh
# Grow the root partition/filesystem on first boot (Slackware rc.local hook).
[ -e /etc/slackware-usb-grow-done ] && exit 0
root_src="$(findmnt -nro SOURCE / 2>/dev/null)"
[ -n "$root_src" ] || exit 0
part=$(echo "$root_src" | grep -oE '[0-9]+$')
disk="${root_src%$part}"
case "$disk" in
  *p) disk="${disk%p}" ;;   # /dev/nvme0n1p2 -> /dev/nvme0n1
esac
if command -v growpart >/dev/null 2>&1; then
  growpart "$disk" "$part" 2>/dev/null || true
fi
resize2fs "$root_src" 2>/dev/null || true
touch /etc/slackware-usb-grow-done
chmod -x /etc/rc.d/rc.grow-root
GROW
  chmod 0755 "$ROOTFS/etc/rc.d/rc.grow-root"
  # Hook it from rc.local (Slackware's local boot hook).
  touch "$ROOTFS/etc/rc.d/rc.local"
  grep -q rc.grow-root "$ROOTFS/etc/rc.d/rc.local" 2>/dev/null || \
    printf '\n[ -x /etc/rc.d/rc.grow-root ] && /etc/rc.d/rc.grow-root\n' >> "$ROOTFS/etc/rc.d/rc.local"
  chmod 0755 "$ROOTFS/etc/rc.d/rc.local" 2>/dev/null || true
fi

# --- /etc/fstab ---
ROOT_UUID="$(uuidgen)"
ESP_ID="$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n' | tr '[:lower:]' '[:upper:]')"
ESP_UUID="${ESP_ID:0:4}-${ESP_ID:4:4}"
mkdir -p "$ROOTFS/boot/efi"
cat > "$ROOTFS/etc/fstab" <<FSTAB
UUID=$ROOT_UUID  /          ext4  defaults,noatime  0 1
UUID=$ESP_UUID   /boot/efi  vfat  umask=0077        0 2
proc             /proc      proc  defaults          0 0
tmpfs            /tmp       tmpfs defaults,nosuid,nodev 0 0
FSTAB

# --- Build the initrd (chroot APIs already mounted above) ---
kver=$(find "$ROOTFS/lib/modules" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null | sort | tail -n1)
[ -n "$kver" ] || fail "No Slackware kernel modules found under /lib/modules"
log "Detected kernel $kver"

# Pick the kernel image matching the requested flavor (fall back to whatever exists).
kern_basename="vmlinuz-generic"
[ "$KERNEL_FLAVOR" = "huge" ] && kern_basename="vmlinuz-huge"
kern_path=$(find "$ROOTFS/boot" -maxdepth 1 -name "$kern_basename-*" | sort | tail -n1)
if [ -z "$kern_path" ]; then
  kern_path=$(find "$ROOTFS/boot" -maxdepth 1 -name 'vmlinuz-*' | sort | tail -n1)
  [ -n "$kern_path" ] || fail "No Slackware kernel image found in /boot"
fi
ln -sf "$(basename "$kern_path")" "$ROOTFS/boot/vmlinuz"

log "Generating initrd with mkinitrd (ext4 + USB support)"
chroot "$ROOTFS" mkinitrd -c -m ext4 -k "$kver" -f ext4 -r "UUID=$ROOT_UUID" -u -o /boot/initrd.gz 2>&1 | tail -5 || \
  fail "mkinitrd failed to create /boot/initrd.gz"
[ -s "$ROOTFS/boot/initrd.gz" ] || fail "initrd was not created"
ln -sf initrd.gz "$ROOTFS/boot/initrd"

cleanup_chroot_mounts

# --- Build a standalone GRUB EFI binary + grub.cfg (removable UEFI boot) ---
cat > "$GRUB_CFG" <<EOF
set default=0
set timeout=$BOOT_TIMEOUT
set timeout_style=menu

menuentry 'Slackware Linux USB' {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz root=UUID=$ROOT_UUID ro rootfstype=ext4 rootwait
    initrd /boot/initrd.gz
}

menuentry 'Slackware Linux USB (safe graphics)' {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz root=UUID=$ROOT_UUID ro rootfstype=ext4 rootwait nomodeset
    initrd /boot/initrd.gz
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

# --- Create the raw GPT image and embed the partitions ---
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
[ -n "$ESP_OFFSET" ] && [ -n "$ESP_SIZE" ] && [ -n "$ROOT_OFFSET" ] && [ -n "$ROOT_SIZE" ] || \
  fail "Could not parse generated GPT partition layout"

truncate -s "$ESP_SIZE" "$ESP_IMG"
mkfs.vfat -F 32 -n EFI -i "$ESP_ID" "$ESP_IMG" >/dev/null
mmd -i "$ESP_IMG" ::/EFI >/dev/null 2>&1 || true
mmd -i "$ESP_IMG" ::/EFI/BOOT >/dev/null 2>&1 || true
mmd -i "$ESP_IMG" ::/grub >/dev/null 2>&1 || true
mcopy -o -i "$ESP_IMG" "$BOOT_EFI" ::/EFI/BOOT/BOOTX64.EFI
mcopy -o -i "$ESP_IMG" "$GRUB_CFG" ::/grub/grub.cfg

log "Packing Slackware root filesystem into ext4 image"
truncate -s "$ROOT_SIZE" "$ROOT_IMG"
mkfs.ext4 -F -U "$ROOT_UUID" -L slackware-root -d "$ROOTFS" "$ROOT_IMG" >/dev/null

log "Embedding ESP and root partitions"
dd if="$ESP_IMG" of="$TMP_OUTPUT" bs=512 seek=$((ESP_OFFSET / 512)) conv=notrunc status=none
dd if="$ROOT_IMG" of="$TMP_OUTPUT" bs=512 seek=$((ROOT_OFFSET / 512)) conv=notrunc status=none
mv "$TMP_OUTPUT" "$OUTPUT"

log "Slackware image written: $OUTPUT"
cat <<EOF

DONE: $OUTPUT

Image profile:
  distro: Slackware $TREE ($RELEASE)
  desktop: $DESKTOP
  display manager: $DISPLAY_MANAGER
  bootloader: GRUB removable UEFI (/EFI/BOOT/BOOTX64.EFI)
  root UUID: $ROOT_UUID
  user: $USER_NAME
  series: $SERIES

Write to USB:
  sudo dd if="$OUTPUT" of=/dev/sdX bs=16M iflag=fullblock status=progress conv=fsync

Replace /dev/sdX with USB device, not partition.
EOF
