#!/bin/sh
# Validate and plan a Slackware USB image configuration.
# Full chroot/image assembly is intentionally separate from Alpine's builder; today this
# script provides dry-run package resolution and safe config validation for the Slackware backend.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
safe_token() {
  name="$1"; value="$2"
  case "$value" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;; esac
}
safe_optional_token() { [ -z "$2" ] || safe_token "$1" "$2"; }

USER_NAME="${ALPINE_USB_USER:-slackware}"
HOSTNAME="${ALPINE_USB_HOSTNAME:-slackware-usb}"
TIMEZONE="${ALPINE_USB_TIMEZONE:-UTC}"
LOCALE="${ALPINE_USB_LOCALE:-en_US.UTF-8}"
CONSOLE_KEYMAP="${ALPINE_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${ALPINE_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${ALPINE_USB_XKB_VARIANT:-}"
XKB_MODEL="${ALPINE_USB_XKB_MODEL:-pc105}"
DESKTOP="$(lower "${ALPINE_USB_DESKTOP:-xfce}")"
TILING_WMS="${ALPINE_USB_TILING_WMS:-}"
DEFAULT_SESSION="$(lower "${ALPINE_USB_DEFAULT_SESSION:-auto}")"
DISPLAY_MANAGER="$(lower "${ALPINE_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${ALPINE_USB_NETWORK:-networkmanager}")"
WIFI="${ALPINE_USB_WIFI:-1}"
BLUETOOTH="${ALPINE_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${ALPINE_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${ALPINE_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${ALPINE_USB_FIRMWARE:-full}")"
BOOTLOADER="$(lower "${ALPINE_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${ALPINE_USB_KERNEL_FLAVOR:-generic}")"
BOOT_TIMEOUT="${ALPINE_USB_BOOT_TIMEOUT:-3}"
AUTO_RESIZE="${ALPINE_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${ALPINE_USB_EXTRA_PACKAGES:-}"
RELEASE="${SLACKWARE_RELEASE:-stable}"
ARCH="${ARCH:-x86_64}"
DRY_RUN="${ALPINE_USB_DRY_RUN:-0}"

case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"
safe_token "Locale" "$LOCALE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"
safe_token "XKB layout" "$XKB_LAYOUT"
safe_optional_token "XKB variant" "$XKB_VARIANT"
safe_token "XKB model" "$XKB_MODEL"
case "$BOOT_TIMEOUT" in *[!0-9]*|"") die "Boot timeout must be a number" ;; esac
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac
case "$RELEASE" in stable|current|[0-9]*.[0-9]*) ;; *) die "Unsupported Slackware release: $RELEASE" ;; esac
case "$ARCH" in x86_64) ;; *) die "Slackware backend currently supports x86_64 only" ;; esac
case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt|none) ;; *) die "Unsupported desktop: $DESKTOP" ;; esac
case "$DISPLAY_MANAGER" in auto|lightdm|sddm|gdm|lxdm|greetd|none) ;; *) die "Unsupported display manager: $DISPLAY_MANAGER" ;; esac
case "$NETWORK_BACKEND" in networkmanager|none) ;; *) die "Unsupported network backend: $NETWORK_BACKEND" ;; esac
case "$AUDIO" in pipewire|alsa|none) ;; *) die "Unsupported audio option: $AUDIO" ;; esac
case "$BROWSER" in firefox-esr|firefox|chromium|none) ;; *) die "Unsupported browser: $BROWSER" ;; esac
case "$FIRMWARE" in full|none) ;; *) die "Unsupported firmware option: $FIRMWARE" ;; esac
case "$BOOTLOADER" in grub|elilo|syslinux|systemd-boot|systemdboot) ;; *) die "Unsupported bootloader: $BOOTLOADER" ;; esac
case "$KERNEL_FLAVOR" in huge|generic|lts|stable) ;; *) die "Unsupported kernel flavor: $KERNEL_FLAVOR" ;; esac
case "$DEFAULT_SESSION" in auto|xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac

if [ "$DESKTOP" = "gnome" ]; then
  echo "WARN: GNOME is not in the official Slackware package tree; dry-run keeps the requested package name visible." >&2
fi

python3 - <<'PY'
import os
from alpine_usb.slackware_packages.index import release_path
from alpine_usb.slackware_packages.selection import slackware_package_set

config = {
    "desktop": os.environ.get("ALPINE_USB_DESKTOP", "xfce"),
    "display_manager": os.environ.get("ALPINE_USB_DISPLAY_MANAGER", "auto"),
    "default_session": os.environ.get("ALPINE_USB_DEFAULT_SESSION", "auto"),
    "wms": os.environ.get("ALPINE_USB_TILING_WMS", ""),
    "network": os.environ.get("ALPINE_USB_NETWORK", "networkmanager"),
    "wifi": os.environ.get("ALPINE_USB_WIFI", "1"),
    "bluetooth": os.environ.get("ALPINE_USB_BLUETOOTH", "1"),
    "audio": os.environ.get("ALPINE_USB_AUDIO", "pipewire"),
    "browser": os.environ.get("ALPINE_USB_BROWSER", "firefox"),
    "firmware": os.environ.get("ALPINE_USB_FIRMWARE", "full"),
    "kernel": os.environ.get("ALPINE_USB_KERNEL_FLAVOR", "generic"),
    "auto_resize": os.environ.get("ALPINE_USB_AUTO_RESIZE", "1"),
    "extra_packages": os.environ.get("ALPINE_USB_EXTRA_PACKAGES", ""),
}
release = os.environ.get("SLACKWARE_RELEASE", "stable")
arch = os.environ.get("ARCH", "x86_64")
print("Slackware USB configuration dry-run")
print(f"Release: {release} ({release_path(release, arch)}) / {arch}")
print("Package source: official PACKAGES.TXT/slackpkg mirror metadata")
print("Packages:")
for package in slackware_package_set(config):
    print(f"  {package}")
PY

case "$(lower "$DRY_RUN")" in
  1|yes|true|on|enabled) exit 0 ;;
esac

die "Slackware full image assembly is not implemented yet; use --dry-run for validated package/config planning."
