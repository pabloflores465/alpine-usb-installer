#!/bin/sh
# Gentoo configuration planner/validator. In dry-run mode this provides the
# same safety boundary as the Alpine configurator without mutating a target
# root. Non-dry-run is intended to run inside a mounted stage3 root once the
# Gentoo image builder is completed.
set -eu

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
if [ "$DEFAULT_SESSION" = "auto" ]; then if [ "$DESKTOP" != "none" ]; then DEFAULT_SESSION="$DESKTOP"; else set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; fi; fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac
if [ "$DISPLAY_MANAGER" = "auto" ]; then case "$DESKTOP" in gnome) DISPLAY_MANAGER="gdm" ;; plasma|lxqt) DISPLAY_MANAGER="sddm" ;; xfce|mate) DISPLAY_MANAGER="lightdm" ;; none) if [ -n "$TILING_WMS" ]; then DISPLAY_MANAGER="greetd"; else DISPLAY_MANAGER="none"; fi ;; esac; fi

append_packages sys-apps/baselayout sys-apps/openrc app-admin/sudo app-admin/doas app-shells/bash app-editors/vim net-misc/curl net-misc/wget dev-vcs/git sys-fs/e2fsprogs sys-fs/dosfstools sys-apps/util-linux sys-kernel/gentoo-kernel-bin
[ "$FIRMWARE" = "full" ] && append_packages sys-kernel/linux-firmware
case "$BOOTLOADER" in grub) append_packages sys-boot/grub sys-boot/efibootmgr ;; systemd-boot) append_packages sys-apps/systemd sys-boot/efibootmgr ;; esac
if [ "$DESKTOP" != "none" ] || [ -n "$TILING_WMS" ]; then append_packages x11-base/xorg-server x11-drivers/xf86-input-libinput media-libs/mesa; fi
case "$DESKTOP" in xfce) append_packages xfce-base/xfce4-meta x11-terms/xfce4-terminal ;; gnome) append_packages gnome-base/gnome ;; plasma) append_packages kde-plasma/plasma-meta kde-apps/konsole ;; mate) append_packages mate-base/mate ;; lxqt) append_packages lxqt-base/lxqt-meta ;; none) ;; esac
case "$DISPLAY_MANAGER" in lightdm) append_packages x11-misc/lightdm x11-misc/lightdm-gtk-greeter ;; sddm) append_packages x11-misc/sddm ;; gdm) append_packages gnome-base/gdm ;; lxdm) append_packages lxde-base/lxdm ;; greetd) append_packages gui-libs/greetd gui-apps/tuigreet ;; none) ;; esac
for wm in $TILING_WMS; do case "$wm" in i3) append_packages x11-wm/i3 ;; sway) append_packages gui-wm/sway ;; hyprland) append_packages gui-wm/hyprland ;; awesome) append_packages x11-wm/awesome ;; bspwm) append_packages x11-wm/bspwm ;; openbox) append_packages x11-wm/openbox ;; labwc) append_packages gui-wm/labwc ;; esac; done
case "$BROWSER" in firefox) append_packages www-client/firefox ;; firefox-esr) append_packages www-client/firefox-bin ;; chromium) append_packages www-client/chromium ;; none) ;; esac
case "$AUDIO" in pipewire) append_packages media-video/pipewire media-session/wireplumber ;; alsa) append_packages media-libs/alsa-lib media-sound/alsa-utils ;; none) ;; esac
[ "$NETWORK_BACKEND" = "networkmanager" ] && append_packages net-misc/networkmanager
is_enabled "$WIFI" && append_packages net-wireless/wpa_supplicant net-wireless/iw
is_enabled "$BLUETOOTH" && append_packages net-wireless/bluez
is_enabled "$LEGACY_X11_DRIVERS" && append_packages x11-drivers/xf86-video-amdgpu x11-drivers/xf86-video-nouveau x11-drivers/xf86-video-vesa
is_enabled "$AUTO_RESIZE" && append_packages sys-fs/growpart
for pkg in $EXTRA_PACKAGES; do append_packages "$pkg"; done

if is_enabled "$DRY_RUN"; then
  echo "Gentoo USB dry-run OK"
  echo "Stage3: $STAGE3_BRANCH amd64 openrc (default base)"
  echo "Desktop/session: $DESKTOP / $DEFAULT_SESSION, display manager: $DISPLAY_MANAGER"
  echo "Boot: $BOOTLOADER, kernel package: sys-kernel/gentoo-kernel-bin, firmware: $FIRMWARE"
  # shellcheck disable=SC2086
  set -- $PACKAGES
  echo "Package count: $#"
  echo "Packages:$PACKAGES"
  exit 0
fi

die "Gentoo non-dry-run target configuration is not wired yet; use --dry-run or Alpine build path. See docs/gentoo.md."
