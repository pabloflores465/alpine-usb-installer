#!/bin/sh
# Validate and render the openSUSE USB package/configuration plan.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }
safe_token() { name="$1"; value="$2"; case "$value" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;; esac; }
safe_optional_token() { [ -z "$2" ] || safe_token "$1" "$2"; }
safe_package_name() { case "$1" in ""|-*|*[!A-Za-z0-9+_.-]*) die "Invalid package name: $1" ;; esac; }
append_packages() { for pkg in "$@"; do [ -n "$pkg" ] || continue; case " $PACKAGES " in *" $pkg "*) ;; *) PACKAGES="$PACKAGES $pkg" ;; esac; done; }
read_secret_value() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var:-}"; eval "direct_value=\${$value_var:-}"
  if [ -n "$file_value" ]; then [ -f "$file_value" ] || die "Secret file not found: $file_value"; cat "$file_value"
  elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"
  else printf '%s' "$default_value"; fi
}

PACKAGES=""
USER_NAME="${OPENSUSE_USB_USER:-linux}"
USER_PASSWORD="$(read_secret_value OPENSUSE_USB_PASSWORD_FILE OPENSUSE_USB_PASSWORD linux)"
ROOT_PASSWORD="$(read_secret_value OPENSUSE_USB_ROOT_PASSWORD_FILE OPENSUSE_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${OPENSUSE_USB_HOSTNAME:-ledit-opensuse}"
TIMEZONE="${OPENSUSE_USB_TIMEZONE:-UTC}"
LOCALE="${OPENSUSE_USB_LOCALE:-en_US.UTF-8}"
CONSOLE_KEYMAP="${OPENSUSE_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${OPENSUSE_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${OPENSUSE_USB_XKB_VARIANT:-}"
XKB_MODEL="${OPENSUSE_USB_XKB_MODEL:-pc105}"
RELEASE="$(lower "${OPENSUSE_RELEASE:-tumbleweed}")"
DESKTOP="$(lower "${OPENSUSE_USB_DESKTOP:-xfce}")"
TILING_WMS="$(printf '%s' "${OPENSUSE_USB_TILING_WMS:-}" | tr ',;:' '   ')"
DEFAULT_SESSION="$(lower "${OPENSUSE_USB_DEFAULT_SESSION:-auto}")"
DISPLAY_MANAGER="$(lower "${OPENSUSE_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${OPENSUSE_USB_NETWORK:-networkmanager}")"
WIFI="${OPENSUSE_USB_WIFI:-1}"
BLUETOOTH="${OPENSUSE_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${OPENSUSE_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${OPENSUSE_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${OPENSUSE_USB_FIRMWARE:-full}")"
BOOTLOADER="$(lower "${OPENSUSE_USB_BOOTLOADER:-grub}")"
AUTO_RESIZE="${OPENSUSE_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${OPENSUSE_USB_EXTRA_PACKAGES:-}"
DRY_RUN="${OPENSUSE_USB_DRY_RUN:-0}"

case "$RELEASE" in tumbleweed|leap-15.6|leap-16.0) ;; *) die "Unsupported openSUSE release: $RELEASE" ;; esac
case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"; safe_token "Locale" "$LOCALE"; safe_token "Console keymap" "$CONSOLE_KEYMAP"
safe_token "XKB layout" "$XKB_LAYOUT"; safe_optional_token "XKB variant" "$XKB_VARIANT"; safe_token "XKB model" "$XKB_MODEL"
case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt|none) ;; *) die "Unsupported desktop: $DESKTOP" ;; esac
case "$DISPLAY_MANAGER" in auto|lightdm|sddm|gdm|lxdm|greetd|none) ;; *) die "Unsupported display manager: $DISPLAY_MANAGER" ;; esac
case "$NETWORK_BACKEND" in networkmanager|none) ;; *) die "Unsupported network backend: $NETWORK_BACKEND" ;; esac
case "$AUDIO" in pipewire|alsa|none) ;; *) die "Unsupported audio option: $AUDIO" ;; esac
case "$BROWSER" in firefox-esr|firefox|chromium|none) ;; *) die "Unsupported browser: $BROWSER" ;; esac
case "$FIRMWARE" in full|none) ;; *) die "Unsupported firmware option: $FIRMWARE" ;; esac
case "$BOOTLOADER" in grub|systemd-boot|systemdboot) ;; *) die "Unsupported bootloader: $BOOTLOADER" ;; esac
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac
VALID_WMS="i3 sway hyprland awesome bspwm openbox labwc"
for wm in $TILING_WMS; do case " $VALID_WMS " in *" $wm "*) ;; *) die "Unsupported window manager: $wm" ;; esac; done
if [ "$DEFAULT_SESSION" = auto ]; then [ "$DESKTOP" != none ] && DEFAULT_SESSION="$DESKTOP" || { set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; }; fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac
[ "$DISPLAY_MANAGER" = auto ] && case "$DESKTOP" in gnome) DISPLAY_MANAGER=gdm ;; plasma|lxqt) DISPLAY_MANAGER=sddm ;; xfce|mate) DISPLAY_MANAGER=lightdm ;; none) [ -n "$TILING_WMS" ] && DISPLAY_MANAGER=greetd || DISPLAY_MANAGER=none ;; esac

append_packages patterns-base-base kernel-default dracut systemd udev grub2 grub2-x86_64-efi shim sudo bash curl wget vim timezone ca-certificates e2fsprogs dosfstools
is_enabled "$AUTO_RESIZE" && append_packages growpart
[ "$NETWORK_BACKEND" = networkmanager ] && append_packages NetworkManager
is_enabled "$WIFI" && append_packages wpa_supplicant iw wireless-regdb
is_enabled "$BLUETOOTH" && append_packages bluez blueman
[ "$FIRMWARE" = full ] && append_packages kernel-firmware-all
case "$DESKTOP" in xfce) append_packages patterns-xfce-xfce xfce4-session ;; gnome) append_packages patterns-gnome-gnome ;; plasma) append_packages patterns-kde-kde_plasma plasma6-session ;; mate) append_packages patterns-mate-mate ;; lxqt) append_packages patterns-lxqt-lxqt ;; esac
for wm in $TILING_WMS; do append_packages "$wm"; done
case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm|greetd) append_packages "$DISPLAY_MANAGER" ;; esac
case "$AUDIO" in pipewire) append_packages pipewire wireplumber pipewire-pulseaudio ;; alsa) append_packages alsa ;; esac
case "$BROWSER" in firefox|firefox-esr) append_packages MozillaFirefox ;; chromium) append_packages chromium ;; esac
[ "$BOOTLOADER" = systemd-boot ] && append_packages systemd-boot
for pkg in $EXTRA_PACKAGES; do safe_package_name "$pkg"; append_packages "$pkg"; done
[ -n "${OPENSUSE_USB_PACKAGE_PLAN:-}" ] && PACKAGES="$OPENSUSE_USB_PACKAGE_PLAN"

cat <<EOF
openSUSE USB configuration plan
Release: $RELEASE
User: $USER_NAME
Host: $HOSTNAME
Locale: $LOCALE timezone=$TIMEZONE keymap=$CONSOLE_KEYMAP xkb=$XKB_LAYOUT
Desktop: $DESKTOP session=$DEFAULT_SESSION dm=$DISPLAY_MANAGER wms=$TILING_WMS
Network: $NETWORK_BACKEND wifi=$WIFI bluetooth=$BLUETOOTH audio=$AUDIO browser=$BROWSER
Boot: $BOOTLOADER firmware=$FIRMWARE auto_resize=$AUTO_RESIZE
Packages:$PACKAGES
EOF
if is_enabled "$DRY_RUN"; then exit 0; fi
