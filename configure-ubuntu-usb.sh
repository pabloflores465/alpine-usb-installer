#!/bin/sh
# Validate and configure Ubuntu USB images. In dry-run mode this prints the
# resolved apt package set without touching a target root.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

is_enabled() {
  case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac
}

normalize_words() { printf '%s' "${1:-}" | tr ',;:' '   ' | tr '\n\t' '  '; }
has_word() { needle="$1"; words=" $2 "; case "$words" in *" $needle "*) return 0 ;; *) return 1 ;; esac; }

PACKAGES=""
append_packages() {
  for pkg in "$@"; do
    [ -n "$pkg" ] || continue
    case " $PACKAGES " in *" $pkg "*) ;; *) PACKAGES="$PACKAGES $pkg" ;; esac
  done
}

safe_token() { name="$1"; value="$2"; case "$value" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;; esac; }
safe_optional_token() { [ -z "$2" ] || safe_token "$1" "$2"; }
safe_package_name() { case "$1" in ""|-*|*[!A-Za-z0-9+_.-]*) die "Invalid package name: $1" ;; esac; }

read_secret_value() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var:-}"
  eval "direct_value=\${$value_var:-}"
  if [ -n "$file_value" ]; then
    [ -f "$file_value" ] || die "Secret file not found: $file_value"
    cat "$file_value"
  elif [ -n "$direct_value" ]; then
    printf '%s' "$direct_value"
  else
    printf '%s' "$default_value"
  fi
}

RELEASE="$(lower "${UBUNTU_RELEASE:-24.04}")"
case "$RELEASE" in 24.04|noble) RELEASE="noble" ;; 22.04|jammy) RELEASE="jammy" ;; *) die "Unsupported Ubuntu release: $RELEASE" ;; esac
USER_NAME="${UBUNTU_USB_USER:-ubuntu}"
USER_PASSWORD="$(read_secret_value UBUNTU_USB_PASSWORD_FILE UBUNTU_USB_PASSWORD ubuntu)"
ROOT_PASSWORD="$(read_secret_value UBUNTU_USB_ROOT_PASSWORD_FILE UBUNTU_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${UBUNTU_USB_HOSTNAME:-ubuntu-usb}"
TIMEZONE="${UBUNTU_USB_TIMEZONE:-UTC}"
LOCALE="${UBUNTU_USB_LOCALE:-en_US.UTF-8}"
LANGUAGE_VALUE="${UBUNTU_USB_LANGUAGE:-${LOCALE%%.*}:en}"
CONSOLE_KEYMAP="${UBUNTU_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${UBUNTU_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${UBUNTU_USB_XKB_VARIANT:-}"
XKB_MODEL="${UBUNTU_USB_XKB_MODEL:-pc105}"
DESKTOP="$(lower "${UBUNTU_USB_DESKTOP:-xfce}")"
TILING_WMS="$(normalize_words "${UBUNTU_USB_TILING_WMS:-}")"
DEFAULT_SESSION="$(lower "${UBUNTU_USB_DEFAULT_SESSION:-auto}")"
DISPLAY_MANAGER="$(lower "${UBUNTU_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${UBUNTU_USB_NETWORK:-networkmanager}")"
WIFI="${UBUNTU_USB_WIFI:-1}"
BLUETOOTH="${UBUNTU_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${UBUNTU_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${UBUNTU_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${UBUNTU_USB_FIRMWARE:-full}")"
LEGACY_X11_DRIVERS="${UBUNTU_USB_LEGACY_X11_DRIVERS:-1}"
PROFILE="${UBUNTU_USB_PROFILE:-compatibility}"
BOOTLOADER="$(lower "${UBUNTU_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${UBUNTU_USB_KERNEL_FLAVOR:-lts}")"
BOOT_TIMEOUT="${UBUNTU_USB_BOOT_TIMEOUT:-3}"
SYSTEMD_BOOT_CONSOLE_MODE="${UBUNTU_USB_SYSTEMD_BOOT_CONSOLE_MODE:-max}"
AUTO_RESIZE="${UBUNTU_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${UBUNTU_USB_EXTRA_PACKAGES:-}"
DRY_RUN="${UBUNTU_USB_DRY_RUN:-0}"
TARGET_ROOT="${UBUNTU_USB_TARGET_ROOT:-}"

case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"; safe_token "Locale" "$LOCALE"; safe_token "Language" "$LANGUAGE_VALUE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"; safe_token "XKB layout" "$XKB_LAYOUT"; safe_optional_token "XKB variant" "$XKB_VARIANT"; safe_token "XKB model" "$XKB_MODEL"
case "$BOOT_TIMEOUT" in *[!0-9]*|"") die "Boot timeout must be a number" ;; esac
case "$SYSTEMD_BOOT_CONSOLE_MODE" in keep|auto|max|[0-9]|[0-9][0-9]) ;; *) die "Unsupported systemd-boot console mode: $SYSTEMD_BOOT_CONSOLE_MODE" ;; esac
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac
case "$(lower "$LEGACY_X11_DRIVERS")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported legacy X11 drivers value: $LEGACY_X11_DRIVERS" ;; esac
case "$PROFILE" in compatibility|minimal|"") ;; *) die "Unsupported profile: $PROFILE" ;; esac
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

if [ "$DEFAULT_SESSION" = "auto" ]; then
  if [ "$DESKTOP" != "none" ]; then DEFAULT_SESSION="$DESKTOP"; else set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; fi
fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac
if [ "$DISPLAY_MANAGER" = "auto" ]; then
  case "$DESKTOP" in gnome) DISPLAY_MANAGER="gdm" ;; plasma|lxqt) DISPLAY_MANAGER="sddm" ;; xfce|mate) DISPLAY_MANAGER="lightdm" ;; none) if [ -n "$TILING_WMS" ]; then DISPLAY_MANAGER="greetd"; else DISPLAY_MANAGER="none"; fi ;; esac
fi
case "$DEFAULT_SESSION" in shell) case "$DISPLAY_MANAGER" in none|greetd) ;; *) die "A graphical display manager needs a desktop or WM session" ;; esac ;; sway|hyprland|labwc) case "$DISPLAY_MANAGER" in lightdm|lxdm) die "Wayland sessions require greetd, SDDM, GDM or no display manager" ;; esac ;; esac

append_packages ubuntu-minimal linux-generic systemd-sysv dbus dbus-user-session sudo bash zsh curl wget git nano vim htop less ca-certificates tzdata locales console-setup keyboard-configuration e2fsprogs dosfstools util-linux udev policykit-1 fonts-noto-color-emoji fonts-dejavu-core
[ "$KERNEL_FLAVOR" = "lts" ] && append_packages linux-generic || append_packages linux-generic-hwe-24.04
is_enabled "$AUTO_RESIZE" && append_packages cloud-guest-utils initramfs-tools
[ "$FIRMWARE" = "full" ] && append_packages linux-firmware
case "$BOOTLOADER" in grub) append_packages grub-efi-amd64 grub-pc-bin efibootmgr ;; systemd-boot) append_packages systemd-boot efibootmgr ;; esac
GRAPHICAL=0; if [ "$DESKTOP" != "none" ] || [ -n "$TILING_WMS" ]; then GRAPHICAL=1; fi; case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm) GRAPHICAL=1 ;; esac
if [ "$GRAPHICAL" = "1" ]; then
  append_packages xorg xinit x11-xserver-utils xkb-data libinput-tools mesa-utils xdg-utils
  is_enabled "$LEGACY_X11_DRIVERS" && append_packages xserver-xorg-video-all xserver-xorg-input-all
fi
case "$DESKTOP" in xfce) append_packages xfce4 xfce4-terminal xfce4-screensaver thunar-volman gvfs udisks2 ;; gnome) append_packages ubuntu-desktop-minimal gnome-terminal ;; plasma) append_packages kde-plasma-desktop konsole dolphin ;; mate) append_packages ubuntu-mate-desktop mate-terminal gvfs udisks2 ;; lxqt) append_packages lubuntu-desktop qterminal pcmanfm-qt gvfs udisks2 ;; none) ;; esac
for wm in $TILING_WMS; do case "$wm" in i3) append_packages i3 i3status i3lock suckless-tools xterm feh picom policykit-1-gnome ;; sway) append_packages sway swaybg swayidle swaylock foot waybar mako-notifier grim slurp xwayland xdg-desktop-portal-wlr policykit-1-gnome ;; hyprland) append_packages hyprland foot waybar mako-notifier xwayland xdg-desktop-portal policykit-1-gnome ;; awesome) append_packages awesome xterm rofi picom policykit-1-gnome ;; bspwm) append_packages bspwm sxhkd polybar xterm suckless-tools feh picom policykit-1-gnome ;; openbox) append_packages openbox tint2 xterm suckless-tools feh picom policykit-1-gnome ;; labwc) append_packages labwc foot swaybg waybar mako-notifier xdg-desktop-portal-wlr policykit-1-gnome ;; esac; done
case "$DISPLAY_MANAGER" in lightdm) append_packages lightdm lightdm-gtk-greeter accountsservice ;; sddm) append_packages sddm accountsservice ;; gdm) append_packages gdm3 accountsservice ;; lxdm) append_packages lxdm ;; greetd) append_packages greetd tuigreet ;; none) ;; esac
if [ "$NETWORK_BACKEND" = "networkmanager" ]; then append_packages network-manager; is_enabled "$WIFI" && append_packages wireless-regdb wpasupplicant; fi
is_enabled "$BLUETOOTH" && append_packages bluez blueman
case "$AUDIO" in pipewire) append_packages pipewire pipewire-pulse wireplumber alsa-utils pavucontrol ;; alsa) append_packages alsa-utils ;; none) ;; esac
case "$BROWSER" in firefox|firefox-esr) append_packages firefox ;; chromium) append_packages chromium-browser ;; none) ;; esac
for pkg in $EXTRA_PACKAGES; do safe_package_name "$pkg"; append_packages "$pkg"; done

if is_enabled "$DRY_RUN"; then
  echo "Ubuntu USB dry-run"
  echo "Release: $RELEASE"
  echo "Desktop: $DESKTOP session=$DEFAULT_SESSION display-manager=$DISPLAY_MANAGER"
  echo "Packages:$PACKAGES"
  exit 0
fi

[ -n "$TARGET_ROOT" ] || die "UBUNTU_USB_TARGET_ROOT is required unless UBUNTU_USB_DRY_RUN=1"
[ -d "$TARGET_ROOT" ] || die "Target root not found: $TARGET_ROOT"
printf '%s\n' "$HOSTNAME" >"$TARGET_ROOT/etc/hostname"
cat >"$TARGET_ROOT/etc/default/locale" <<EOF_LOCALE
LANG=$LOCALE
LANGUAGE=$LANGUAGE_VALUE
EOF_LOCALE
cat >"$TARGET_ROOT/etc/default/keyboard" <<EOF_KBD
XKBMODEL="$XKB_MODEL"
XKBLAYOUT="$XKB_LAYOUT"
XKBVARIANT="$XKB_VARIANT"
XKBOPTIONS=""
BACKSPACE="guess"
EOF_KBD
cat >"$TARGET_ROOT/tmp/linux-usb-packages.list" <<EOF_PACKAGES
$PACKAGES
EOF_PACKAGES
exit 0
