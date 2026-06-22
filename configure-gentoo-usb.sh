#!/bin/sh
# Gentoo configuration planner/installer. Dry-run validates and prints the
# package plan. Non-dry-run runs inside an extracted Gentoo stage3 root.
set -eu

log() { printf '[gentoo-config] %s\n' "$*"; }
die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }
normalize_words() { printf '%s' "${1:-}" | tr ',;:' '   ' | tr '\n\t' '  '; }
has_word() { needle="$1"; words=" $2 "; case "$words" in *" $needle "*) return 0 ;; *) return 1 ;; esac; }
safe_token() { name="$1"; value="$2"; case "$value" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;; esac; }
safe_optional_token() { [ -z "$2" ] && return 0; safe_token "$1" "$2"; }
safe_atom() { atom="$1"; case "$atom" in */*) case "$atom" in *[!A-Za-z0-9+_.-]*/*|*/*[!A-Za-z0-9+_.-]*|"/"*) die "Invalid Gentoo package atom: $atom" ;; esac ;; [A-Za-z0-9]*) case "$atom" in *[!A-Za-z0-9+_.-]*) die "Invalid Gentoo package atom: $atom" ;; esac ;; *) die "Invalid Gentoo package atom: $atom" ;; esac; }
append_packages() { for pkg in "$@"; do [ -n "$pkg" ] || continue; safe_atom "$pkg"; case " $PACKAGES " in *" $pkg "*) ;; *) PACKAGES="$PACKAGES $pkg" ;; esac; done; }
read_secret_value() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var:-}"; eval "direct_value=\${$value_var:-}"
  if [ -n "$file_value" ]; then [ -f "$file_value" ] || die "Secret file not found: $file_value"; cat "$file_value"; elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"; else printf '%s' "$default_value"; fi
}
service_exists() { [ -x "/etc/init.d/$1" ]; }
add_service() { service="$1"; runlevel="${2:-default}"; service_exists "$service" && rc-update add "$service" "$runlevel" >/dev/null 2>&1 || true; }
write_file() { path="$1"; shift; mkdir -p "$(dirname "$path")"; cat > "$path"; }

USER_NAME="${ALPINE_USB_USER:-gentoo}"
USER_PASSWORD="$(read_secret_value ALPINE_USB_PASSWORD_FILE ALPINE_USB_PASSWORD gentoo)"
ROOT_PASSWORD="$(read_secret_value ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${ALPINE_USB_HOSTNAME:-gentoo-usb}"
TIMEZONE="${ALPINE_USB_TIMEZONE:-UTC}"
LOCALE="${ALPINE_USB_LOCALE:-en_US.UTF-8}"
LANGUAGE_VALUE="${ALPINE_USB_LANGUAGE:-${LOCALE%%.*}:en}"
CONSOLE_KEYMAP="${ALPINE_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${ALPINE_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${ALPINE_USB_XKB_VARIANT:-}"
XKB_MODEL="${ALPINE_USB_XKB_MODEL:-pc105}"
DESKTOP="$(lower "${ALPINE_USB_DESKTOP:-xfce}")"
TILING_WMS="$(normalize_words "${ALPINE_USB_TILING_WMS:-}")"
DEFAULT_SESSION="$(lower "${ALPINE_USB_DEFAULT_SESSION:-auto}")"
DISPLAY_MANAGER="$(lower "${ALPINE_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${ALPINE_USB_NETWORK:-networkmanager}")"
WIFI="${ALPINE_USB_WIFI:-1}"
BLUETOOTH="${ALPINE_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${ALPINE_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${ALPINE_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${ALPINE_USB_FIRMWARE:-full}")"
LEGACY_X11_DRIVERS="${ALPINE_USB_LEGACY_X11_DRIVERS:-1}"
PROFILE="${ALPINE_USB_PROFILE:-compatibility}"
BOOTLOADER="$(lower "${ALPINE_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${ALPINE_USB_KERNEL_FLAVOR:-lts}")"
AUTO_RESIZE="${ALPINE_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${ALPINE_USB_EXTRA_PACKAGES:-}"
DRY_RUN="${ALPINE_USB_DRY_RUN:-0}"
STAGE3_BRANCH="${GENTOO_STAGE3_BRANCH:-stable}"
PACKAGES=""

case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"; safe_token "Locale" "$LOCALE"; safe_token "Language" "$LANGUAGE_VALUE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"; safe_token "XKB layout" "$XKB_LAYOUT"; safe_optional_token "XKB variant" "$XKB_VARIANT"; safe_token "XKB model" "$XKB_MODEL"
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac
case "$(lower "$LEGACY_X11_DRIVERS")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported legacy X11 drivers value: $LEGACY_X11_DRIVERS" ;; esac
case "$PROFILE" in compatibility|minimal|"") ;; *) die "Unsupported profile: $PROFILE" ;; esac
case "$STAGE3_BRANCH" in stable|testing) ;; *) die "Gentoo branch must be stable or testing" ;; esac
case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt|none) ;; *) die "Unsupported desktop: $DESKTOP" ;; esac
case "$DISPLAY_MANAGER" in auto|lightdm|sddm|gdm|lxdm|greetd|none) ;; *) die "Unsupported display manager: $DISPLAY_MANAGER" ;; esac
case "$NETWORK_BACKEND" in networkmanager|none) ;; *) die "Unsupported network backend: $NETWORK_BACKEND" ;; esac
case "$AUDIO" in pipewire|alsa|none) ;; *) die "Unsupported audio option: $AUDIO" ;; esac
case "$BROWSER" in firefox-esr|firefox|chromium|none) ;; *) die "Unsupported browser: $BROWSER" ;; esac
case "$FIRMWARE" in full|none) ;; *) die "Unsupported firmware option: $FIRMWARE" ;; esac
case "$BOOTLOADER" in grub|systemd-boot|systemdboot) ;; *) die "Unsupported bootloader: $BOOTLOADER" ;; esac
[ "$BOOTLOADER" = "systemdboot" ] && BOOTLOADER="systemd-boot"
case "$KERNEL_FLAVOR" in lts|stable) ;; *) die "Unsupported kernel flavor: $KERNEL_FLAVOR" ;; esac
VALID_WMS="i3 sway hyprland awesome bspwm openbox labwc"
for wm in $TILING_WMS; do has_word "$wm" "$VALID_WMS" || die "Unsupported window manager: $wm"; done
# shellcheck disable=SC2086 # intentional split: first configured WM becomes default session
if [ "$DEFAULT_SESSION" = "auto" ]; then if [ "$DESKTOP" != "none" ]; then DEFAULT_SESSION="$DESKTOP"; else set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; fi; fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac
if [ "$DISPLAY_MANAGER" = "auto" ]; then case "$DESKTOP" in gnome) DISPLAY_MANAGER="gdm" ;; plasma|lxqt) DISPLAY_MANAGER="sddm" ;; xfce|mate) DISPLAY_MANAGER="lightdm" ;; none) if [ -n "$TILING_WMS" ]; then DISPLAY_MANAGER="greetd"; else DISPLAY_MANAGER="none"; fi ;; esac; fi

append_packages sys-apps/baselayout sys-apps/openrc sys-apps/shadow app-admin/sysklogd app-admin/sudo app-admin/doas app-shells/bash app-editors/vim app-misc/tmux net-misc/curl net-misc/wget dev-vcs/git sys-fs/e2fsprogs sys-fs/dosfstools sys-apps/util-linux sys-block/parted sys-kernel/gentoo-kernel-bin
[ "$FIRMWARE" = "full" ] && append_packages sys-kernel/linux-firmware
case "$BOOTLOADER" in grub) append_packages sys-boot/grub ;; systemd-boot) append_packages sys-apps/systemd sys-boot/efibootmgr ;; esac
if [ "$DESKTOP" != "none" ] || [ -n "$TILING_WMS" ]; then append_packages x11-base/xorg-server x11-drivers/xf86-input-libinput media-libs/mesa; fi
case "$DESKTOP" in xfce) append_packages xfce-base/xfce4-meta x11-terms/xfce4-terminal ;; gnome) append_packages gnome-base/gnome ;; plasma) append_packages kde-plasma/plasma-meta kde-apps/konsole ;; mate) append_packages mate-base/mate ;; lxqt) append_packages lxqt-base/lxqt-meta ;; none) ;; esac
case "$DISPLAY_MANAGER" in lightdm) append_packages x11-misc/lightdm x11-misc/lightdm-gtk-greeter ;; sddm) append_packages x11-misc/sddm ;; gdm) append_packages gnome-base/gdm ;; lxdm) append_packages lxde-base/lxdm ;; greetd) append_packages gui-libs/greetd gui-apps/tuigreet ;; none) ;; esac
for wm in $TILING_WMS; do case "$wm" in i3) append_packages x11-wm/i3 ;; sway) append_packages gui-wm/sway ;; hyprland) append_packages gui-wm/hyprland ;; awesome) append_packages x11-wm/awesome ;; bspwm) append_packages x11-wm/bspwm ;; openbox) append_packages x11-wm/openbox ;; labwc) append_packages gui-wm/labwc ;; esac; done
case "$BROWSER" in firefox|firefox-esr) append_packages www-client/firefox-bin ;; chromium) append_packages www-client/chromium ;; none) ;; esac
case "$AUDIO" in pipewire) append_packages media-video/pipewire media-video/wireplumber ;; alsa) append_packages media-libs/alsa-lib media-sound/alsa-utils ;; none) ;; esac
[ "$NETWORK_BACKEND" = "networkmanager" ] && append_packages net-misc/networkmanager
is_enabled "$WIFI" && append_packages net-wireless/wpa_supplicant net-wireless/iw
is_enabled "$BLUETOOTH" && append_packages net-wireless/bluez
is_enabled "$LEGACY_X11_DRIVERS" && append_packages x11-drivers/xf86-video-amdgpu x11-drivers/xf86-video-nouveau x11-drivers/xf86-video-vesa
for pkg in $EXTRA_PACKAGES; do append_packages "$pkg"; done

if is_enabled "$DRY_RUN"; then
  echo "Gentoo USB dry-run OK"
  echo "Stage3: $STAGE3_BRANCH amd64 openrc"
  echo "Desktop/session: $DESKTOP / $DEFAULT_SESSION, display manager: $DISPLAY_MANAGER"
  echo "Boot: $BOOTLOADER, kernel package: sys-kernel/gentoo-kernel-bin, firmware: $FIRMWARE"
  # shellcheck disable=SC2086
  set -- $PACKAGES
  echo "Package count: $#"
  echo "Packages:$PACKAGES"
  exit 0
fi

[ -f /etc/gentoo-release ] || die "Non-dry-run Gentoo configuration must run inside a Gentoo stage3 root"
[ "$(id -u)" = "0" ] || die "Gentoo configuration must run as root"
[ "$BOOTLOADER" = "grub" ] || die "Gentoo installed image build currently supports GRUB only"

configure_portage() {
  log "Writing Portage defaults"
  mkdir -p /etc/portage/package.use /etc/portage/package.accept_keywords /etc/portage/package.license
  build_jobs="${GENTOO_BUILD_JOBS:-2}"
  case "$build_jobs" in *[!0-9]*|"") build_jobs=2 ;; esac
  jobs="${GENTOO_MAKEOPTS:-}"
  if [ -z "$jobs" ]; then jobs="-j$build_jobs"; fi
  use_flags="${GENTOO_USE_FLAGS:-X wayland elogind dbus policykit udev udisks opengl vulkan alsa pulseaudio bluetooth wifi png jpeg harfbuzz truetype fontconfig gtk gtk3 -vala -introspection -systemd}"
  emerge_opts="--jobs=$build_jobs --load-average=$build_jobs --binpkg-respect-use=y --autounmask-continue=y --autounmask-use=y --autounmask-license=y --autounmask-keep-masks=y --quiet-build=y ${GENTOO_EMERGE_OPTS:-}"
  if is_enabled "${GENTOO_USE_BINPKGS:-1}"; then emerge_opts="--getbinpkg --usepkg $emerge_opts"; fi
  cat >> /etc/portage/make.conf <<EOF

# Linux USB Installer Gentoo image defaults
COMMON_FLAGS="-O2 -pipe"
CFLAGS="\${COMMON_FLAGS}"
CXXFLAGS="\${COMMON_FLAGS}"
FCFLAGS="\${COMMON_FLAGS}"
FFLAGS="\${COMMON_FLAGS}"
MAKEOPTS="$jobs"
ACCEPT_LICENSE="${GENTOO_ACCEPT_LICENSE:-*}"
GRUB_PLATFORMS="efi-64"
VIDEO_CARDS="amdgpu nouveau vesa modesetting intel"
INPUT_DEVICES="libinput"
USE="$use_flags"
FEATURES="${GENTOO_FEATURES:--sandbox -usersandbox -pid-sandbox -network-sandbox}"
EMERGE_DEFAULT_OPTS="$emerge_opts"
EOF
  cat > /etc/portage/package.use/usb-installer <<EOF
# Keep common desktop/browser dependency USE constraints satisfiable.
app-crypt/gcr -vala -introspection
net-misc/networkmanager -bluetooth -modemmanager -ppp -teamd -ovs -introspection
dev-python/pillow -truetype
dev-libs/libdbusmenu gtk3
x11-libs/gdk-pixbuf -introspection
xfce-base/thunar udisks
sys-kernel/installkernel dracut
media-libs/freetype harfbuzz png
media-libs/libvpx postproc
www-client/firefox -system-libvpx
EOF
  if [ "$STAGE3_BRANCH" = "testing" ]; then
    printf '*/* ~amd64\n' > /etc/portage/package.accept_keywords/usb-installer
  fi
}

sync_portage() {
  if ! is_enabled "${GENTOO_EMERGE_SYNC:-1}" && [ -d /var/db/repos/gentoo/profiles ]; then
    log "Skipping Portage sync by request"
    return 0
  fi
  log "Syncing Gentoo repository metadata"
  emerge-webrsync || emerge --sync
}

select_desktop_profile() {
  if [ "$DESKTOP" = "none" ] && [ -z "$TILING_WMS" ]; then
    return 0
  fi
  command -v eselect >/dev/null 2>&1 || return 0
  for profile in \
    default/linux/amd64/23.0/desktop \
    default/linux/amd64/17.1/desktop \
    default/linux/amd64/23.0/split-usr/desktop; do
    if [ -d "/var/db/repos/gentoo/profiles/$profile" ]; then
      log "Selecting Gentoo desktop profile: $profile"
      eselect profile set "$profile" >/dev/null 2>&1 || true
      return 0
    fi
  done
}

print_last_build_log() {
  latest_log="$(find /var/tmp/portage -path '*/temp/build.log' -type f -exec ls -t {} + 2>/dev/null | head -n 1 || true)"
  [ -n "$latest_log" ] || return 0
  log "Last Portage build log tail: $latest_log"
  tail -n 200 "$latest_log" || true
}

install_packages() {
  log "Installing Gentoo packages"
  # Allow stage3 packages to rebuild/update when desktop USE flags (for example
  # elogind on pambase) are required by the selected package set.
  # shellcheck disable=SC2086
  if ! emerge --verbose --update --newuse --deep --with-bdeps=y $PACKAGES; then
    print_last_build_log
    return 1
  fi
}

session_command() {
  case "$DEFAULT_SESSION" in
    xfce) echo "startxfce4" ;;
    gnome) echo "gnome-session" ;;
    plasma) echo "startplasma-x11" ;;
    mate) echo "mate-session" ;;
    lxqt) echo "startlxqt" ;;
    i3) echo "i3" ;;
    sway) echo "sway" ;;
    hyprland) echo "Hyprland" ;;
    awesome) echo "awesome" ;;
    bspwm) echo "bspwm" ;;
    openbox) echo "openbox-session" ;;
    labwc) echo "labwc" ;;
    shell|*) echo "bash" ;;
  esac
}

configure_system() {
  log "Configuring system files, users, and services"
  echo "$HOSTNAME" > /etc/hostname
  cat > /etc/hosts <<EOF
127.0.0.1 localhost
127.0.1.1 $HOSTNAME.localdomain $HOSTNAME
::1 localhost
EOF
  if [ -f "/usr/share/zoneinfo/$TIMEZONE" ]; then ln -snf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime; fi
  echo "$TIMEZONE" > /etc/timezone
  if ! grep -qs "^$LOCALE " /etc/locale.gen 2>/dev/null; then echo "$LOCALE UTF-8" >> /etc/locale.gen; fi
  locale-gen >/dev/null 2>&1 || true
  mkdir -p /etc/env.d
  cat > /etc/env.d/02locale <<EOF
LANG="$LOCALE"
LANGUAGE="$LANGUAGE_VALUE"
EOF
  env-update >/dev/null 2>&1 || true
  mkdir -p /etc/conf.d
  cat > /etc/conf.d/keymaps <<EOF
keymap="$CONSOLE_KEYMAP"
windowkeys="YES"
EOF
  mkdir -p /etc/X11/xorg.conf.d
  cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<EOF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "$XKB_LAYOUT"
    Option "XkbVariant" "$XKB_VARIANT"
    Option "XkbModel" "$XKB_MODEL"
EndSection
EOF
  if ! id "$USER_NAME" >/dev/null 2>&1; then
    useradd -m -s /bin/bash "$USER_NAME"
  fi
  for group in wheel audio video usb plugdev portage input users; do
    getent group "$group" >/dev/null 2>&1 || groupadd -r "$group" >/dev/null 2>&1 || true
    usermod -aG "$group" "$USER_NAME" >/dev/null 2>&1 || true
  done
  printf 'root:%s\n%s:%s\n' "$ROOT_PASSWORD" "$USER_NAME" "$USER_PASSWORD" | chpasswd
  mkdir -p /etc/sudoers.d
  echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/00-wheel
  chmod 440 /etc/sudoers.d/00-wheel
  echo 'permit persist :wheel' > /etc/doas.conf
  chmod 600 /etc/doas.conf

  cmd="$(session_command)"
  home_dir="$(getent passwd "$USER_NAME" | cut -d: -f6)"
  if [ -n "$home_dir" ] && [ -d "$home_dir" ]; then
    cat > "$home_dir/.xinitrc" <<EOF
#!/bin/sh
exec $cmd
EOF
    chown "$USER_NAME" "$home_dir/.xinitrc" >/dev/null 2>&1 || true
    chmod 755 "$home_dir/.xinitrc"
  fi

  add_service sysklogd default
  add_service dbus default
  add_service elogind boot
  [ "$NETWORK_BACKEND" = "networkmanager" ] && add_service NetworkManager default
  is_enabled "$BLUETOOTH" && add_service bluetooth default
  [ "$AUDIO" = "alsa" ] && add_service alsasound default
  case "$DISPLAY_MANAGER" in
    lightdm|sddm|gdm|lxdm)
      cat > /etc/conf.d/xdm <<EOF
DISPLAYMANAGER="$DISPLAY_MANAGER"
EOF
      add_service xdm default
      ;;
    greetd)
      mkdir -p /etc/greetd
      cat > /etc/greetd/config.toml <<EOF
[terminal]
vt = 7

[default_session]
command = "tuigreet --remember --cmd '$cmd'"
user = "greeter"
EOF
      add_service greetd default
      ;;
    none) ;;
  esac
}

configure_autoresize() {
  is_enabled "$AUTO_RESIZE" || return 0
  log "Installing first-boot root auto-resize service"
  cat > /etc/init.d/usb-root-resize <<'EOF'
#!/sbin/openrc-run
description="Grow USB root partition and ext4 filesystem on first boot"

start() {
    root_src="$(findmnt -n -o SOURCE / 2>/dev/null || true)"
    [ -n "$root_src" ] || return 0
    root_src="$(readlink -f "$root_src" 2>/dev/null || printf '%s' "$root_src")"
    [ -b "$root_src" ] || return 0
    case "$root_src" in
        /dev/nvme*n*p[0-9]*|/dev/mmcblk*p[0-9]*) part="${root_src##*p}"; disk="${root_src%p$part}" ;;
        /dev/*[0-9]) part="${root_src##*[!0-9]}"; disk="${root_src%$part}" ;;
        *) return 0 ;;
    esac
    if [ -b "$disk" ] && command -v sfdisk >/dev/null 2>&1; then
        printf ', +\n' | sfdisk --no-reread -N "$part" "$disk" >/dev/null 2>&1 || true
        command -v partprobe >/dev/null 2>&1 && partprobe "$disk" >/dev/null 2>&1 || true
    fi
    command -v resize2fs >/dev/null 2>&1 && resize2fs "$root_src" >/dev/null 2>&1 || true
    rc-update del usb-root-resize default >/dev/null 2>&1 || true
    return 0
}
EOF
  chmod 755 /etc/init.d/usb-root-resize
  rc-update add usb-root-resize default >/dev/null 2>&1 || true
}

clean_build_cache() {
  is_enabled "${GENTOO_CLEAN_BUILD_CACHE:-1}" || return 0
  log "Cleaning Portage build caches from target root"
  rm -rf /var/tmp/portage/* /var/cache/distfiles/* /var/cache/binpkgs/* 2>/dev/null || true
}

configure_portage
sync_portage
select_desktop_profile
install_packages
configure_system
configure_autoresize
clean_build_cache

echo "Gentoo USB install complete"
echo "Packages:$PACKAGES"
