#!/bin/sh
# Configure a Debian root filesystem or validate package/session choices in dry-run mode.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }
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
safe_optional_token() { name="$1"; value="$2"; [ -z "$value" ] && return 0; safe_token "$name" "$value"; }
safe_package_name() { pkg="$1"; case "$pkg" in ""|-*|*[!A-Za-z0-9+_.-]*) die "Invalid package name: $pkg" ;; esac; }
read_secret_value() {
  file_var="$1"; value_var="$2"; default_value="$3"
  eval "file_value=\${$file_var:-}"; eval "direct_value=\${$value_var:-}"
  if [ -n "$file_value" ]; then [ -f "$file_value" ] || die "Secret file not found: $file_value"; cat "$file_value"
  elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"
  else printf '%s' "$default_value"; fi
}

USER_NAME="${DEBIAN_USB_USER:-${LEDIT_USB_USER:-debian}}"
USER_PASSWORD="$(read_secret_value DEBIAN_USB_PASSWORD_FILE DEBIAN_USB_PASSWORD "$(read_secret_value LEDIT_USB_PASSWORD_FILE LEDIT_USB_PASSWORD debian)")"
ROOT_PASSWORD="$(read_secret_value DEBIAN_USB_ROOT_PASSWORD_FILE DEBIAN_USB_ROOT_PASSWORD "$(read_secret_value LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD "$USER_PASSWORD")")"
HOSTNAME="${DEBIAN_USB_HOSTNAME:-${LEDIT_USB_HOSTNAME:-ledit-debian}}"
TIMEZONE="${DEBIAN_USB_TIMEZONE:-${LEDIT_USB_TIMEZONE:-UTC}}"
LOCALE="${DEBIAN_USB_LOCALE:-${LEDIT_USB_LOCALE:-en_US.UTF-8}}"
LANGUAGE_VALUE="${DEBIAN_USB_LANGUAGE:-${LEDIT_USB_LANGUAGE:-${LOCALE%%.*}:en}}"
CONSOLE_KEYMAP="${DEBIAN_USB_CONSOLE_KEYMAP:-${LEDIT_USB_CONSOLE_KEYMAP:-us}}"
XKB_LAYOUT="${DEBIAN_USB_XKB_LAYOUT:-${LEDIT_USB_XKB_LAYOUT:-us}}"
XKB_VARIANT="${DEBIAN_USB_XKB_VARIANT:-${LEDIT_USB_XKB_VARIANT:-}}"
XKB_MODEL="${DEBIAN_USB_XKB_MODEL:-${LEDIT_USB_XKB_MODEL:-pc105}}"
DESKTOP="$(lower "${DEBIAN_USB_DESKTOP:-${LEDIT_USB_DESKTOP:-xfce}}")"
TILING_WMS="$(normalize_words "${DEBIAN_USB_TILING_WMS:-${LEDIT_USB_TILING_WMS:-}}")"
DEFAULT_SESSION="$(lower "${DEBIAN_USB_DEFAULT_SESSION:-${LEDIT_USB_DEFAULT_SESSION:-auto}}")"
DISPLAY_MANAGER="$(lower "${DEBIAN_USB_DISPLAY_MANAGER:-${LEDIT_USB_DISPLAY_MANAGER:-auto}}")"
NETWORK_BACKEND="$(lower "${DEBIAN_USB_NETWORK:-${LEDIT_USB_NETWORK:-networkmanager}}")"
WIFI="${DEBIAN_USB_WIFI:-${LEDIT_USB_WIFI:-1}}"
BLUETOOTH="${DEBIAN_USB_BLUETOOTH:-${LEDIT_USB_BLUETOOTH:-1}}"
AUDIO="$(lower "${DEBIAN_USB_AUDIO:-${LEDIT_USB_AUDIO:-pipewire}}")"
BROWSER="$(lower "${DEBIAN_USB_BROWSER:-${LEDIT_USB_BROWSER:-firefox}}")"
FIRMWARE="$(lower "${DEBIAN_USB_FIRMWARE:-${LEDIT_USB_FIRMWARE:-full}}")"
LEGACY_X11_DRIVERS="${DEBIAN_USB_LEGACY_X11_DRIVERS:-${LEDIT_USB_LEGACY_X11_DRIVERS:-1}}"
PROFILE="${DEBIAN_USB_PROFILE:-${LEDIT_USB_PROFILE:-compatibility}}"
BOOTLOADER="$(lower "${DEBIAN_USB_BOOTLOADER:-${LEDIT_USB_BOOTLOADER:-grub}}")"
KERNEL_FLAVOR="$(lower "${DEBIAN_USB_KERNEL_FLAVOR:-${LEDIT_USB_KERNEL_FLAVOR:-stable}}")"
BOOT_TIMEOUT="${DEBIAN_USB_BOOT_TIMEOUT:-${LEDIT_USB_BOOT_TIMEOUT:-3}}"
AUTO_RESIZE="${DEBIAN_USB_AUTO_RESIZE:-${LEDIT_USB_AUTO_RESIZE:-1}}"
EXTRA_PACKAGES="${DEBIAN_USB_EXTRA_PACKAGES:-${LEDIT_USB_EXTRA_PACKAGES:-}}"
DRY_RUN="${DEBIAN_USB_DRY_RUN:-${LEDIT_USB_DRY_RUN:-0}}"

case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"; safe_token "Locale" "$LOCALE"; safe_token "Language" "$LANGUAGE_VALUE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"; safe_token "XKB layout" "$XKB_LAYOUT"; safe_optional_token "XKB variant" "$XKB_VARIANT"; safe_token "XKB model" "$XKB_MODEL"
case "$BOOT_TIMEOUT" in *[!0-9]*|"") die "Boot timeout must be a number" ;; esac
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
GRAPHICAL=0; if [ "$DESKTOP" != "none" ] || [ -n "$TILING_WMS" ]; then GRAPHICAL=1; fi
case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm) GRAPHICAL=1 ;; esac

append_packages ca-certificates locales tzdata sudo bash zsh curl wget git nano vim htop less dbus dbus-user-session udev polkitd pkexec keyboard-configuration console-setup e2fsprogs dosfstools util-linux fonts-noto fonts-noto-color-emoji
if [ "$KERNEL_FLAVOR" = "lts" ]; then append_packages linux-image-amd64; else append_packages linux-image-amd64; fi
if is_enabled "$AUTO_RESIZE"; then append_packages cloud-guest-utils; fi
if [ "$FIRMWARE" = "full" ]; then append_packages firmware-linux firmware-linux-free firmware-linux-nonfree firmware-misc-nonfree; fi
case "$BOOTLOADER" in grub) append_packages grub-efi-amd64 grub-efi-amd64-bin efibootmgr ;; systemd-boot) append_packages systemd-boot efibootmgr ;; esac
if [ "$GRAPHICAL" = "1" ]; then
  append_packages xorg xinit x11-xserver-utils xkb-data libinput10 mesa-utils xdg-utils dbus-x11
  if is_enabled "$LEGACY_X11_DRIVERS"; then append_packages xserver-xorg-video-amdgpu xserver-xorg-video-ati xserver-xorg-video-intel xserver-xorg-video-nouveau xserver-xorg-video-vesa xserver-xorg-video-fbdev; fi
fi
case "$DESKTOP" in
  xfce) append_packages task-xfce-desktop xfce4-terminal thunar-volman gvfs lxpolkit ;;
  gnome) append_packages task-gnome-desktop gnome-terminal ;;
  plasma) append_packages task-kde-desktop konsole dolphin ;;
  mate) append_packages task-mate-desktop mate-terminal gvfs ;;
  lxqt) append_packages task-lxqt-desktop qterminal pcmanfm-qt gvfs ;;
  none) ;;
esac
for wm in $TILING_WMS; do
  case "$wm" in
    i3) append_packages i3-wm i3status i3lock suckless-tools xterm feh picom lxpolkit ;;
    sway) append_packages sway swaybg swayidle swaylock foot waybar mako-notifier grim slurp xwayland xdg-desktop-portal xdg-desktop-portal-wlr lxpolkit ;;
    hyprland) append_packages hyprland foot waybar mako-notifier xwayland xdg-desktop-portal lxpolkit ;;
    awesome) append_packages awesome xterm rofi picom lxpolkit ;;
    bspwm) append_packages bspwm sxhkd polybar xterm suckless-tools feh picom lxpolkit ;;
    openbox) append_packages openbox tint2 xterm suckless-tools feh picom lxpolkit ;;
    labwc) append_packages labwc foot swaybg waybar mako-notifier xdg-desktop-portal xdg-desktop-portal-wlr lxpolkit ;;
  esac
done
case "$DISPLAY_MANAGER" in lightdm) append_packages lightdm lightdm-gtk-greeter accountsservice ;; sddm) append_packages sddm accountsservice ;; gdm) append_packages gdm3 accountsservice ;; lxdm) append_packages lxdm ;; greetd) append_packages greetd tuigreet ;; none) ;; esac
case "$NETWORK_BACKEND" in networkmanager) append_packages network-manager ;; none) ;; esac
if is_enabled "$WIFI"; then append_packages wireless-regdb wpasupplicant iw; fi
if is_enabled "$BLUETOOTH"; then append_packages bluetooth bluez blueman; fi
case "$AUDIO" in pipewire) append_packages pipewire wireplumber pipewire-pulse pipewire-alsa pavucontrol ;; alsa) append_packages alsa-utils pavucontrol ;; none) ;; esac
case "$BROWSER" in firefox|firefox-esr) append_packages firefox-esr ;; chromium) append_packages chromium ;; none) ;; esac
for pkg in $EXTRA_PACKAGES; do safe_package_name "$pkg"; append_packages "$pkg"; done

if is_enabled "$DRY_RUN"; then
  cat <<EOF
Debian USB dry-run configuration OK
Profile: $PROFILE
Desktop/session: $DESKTOP / $DEFAULT_SESSION
Display manager: $DISPLAY_MANAGER
Bootloader/kernel/firmware: $BOOTLOADER / $KERNEL_FLAVOR / $FIRMWARE
Network: $NETWORK_BACKEND wifi=$WIFI bluetooth=$BLUETOOTH
Audio/browser: $AUDIO / $BROWSER
Packages:$PACKAGES
EOF
  exit 0
fi

ROOT_MOUNT="${DEBIAN_USB_ROOT_MOUNT:-}"
[ -n "$ROOT_MOUNT" ] || die "DEBIAN_USB_ROOT_MOUNT is required when not in dry-run mode"
[ -d "$ROOT_MOUNT" ] || die "Root mount not found: $ROOT_MOUNT"
printf '%s\n' $PACKAGES >"$ROOT_MOUNT/tmp/debian-usb-packages.list"
cat >"$ROOT_MOUNT/tmp/debian-usb-configure-inside.sh" <<'INSIDE'
#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
ensure_apt_components() {
  for file in /etc/apt/sources.list.d/*.sources; do
    [ -f "$file" ] || continue
    sed -i '/^Components:/ {
      / contrib/! s/$/ contrib/
      / non-free/! s/$/ non-free/
      / non-free-firmware/! s/$/ non-free-firmware/
    }' "$file"
  done
  if [ -f /etc/apt/sources.list ]; then
    sed -i '/^[[:space:]]*deb[[:space:]]/ {
      / contrib/! s/$/ contrib/
      / non-free/! s/$/ non-free/
      / non-free-firmware/! s/$/ non-free-firmware/
    }' /etc/apt/sources.list
  fi
}
ensure_apt_components
apt-get update
xargs -r apt-get install -y --no-install-recommends </tmp/debian-usb-packages.list
INSIDE
chmod +x "$ROOT_MOUNT/tmp/debian-usb-configure-inside.sh"
chroot "$ROOT_MOUNT" /tmp/debian-usb-configure-inside.sh
rm -f "$ROOT_MOUNT/tmp/debian-usb-configure-inside.sh" "$ROOT_MOUNT/tmp/debian-usb-packages.list"
echo "$HOSTNAME" >"$ROOT_MOUNT/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 %s\n' "$HOSTNAME" >"$ROOT_MOUNT/etc/hosts"
printf '%s\n' "$TIMEZONE" >"$ROOT_MOUNT/etc/timezone"
cat >"$ROOT_MOUNT/etc/default/locale" <<EOF
LANG=$LOCALE
LANGUAGE=$LANGUAGE_VALUE
EOF
printf 'KEYMAP=%s\n' "$CONSOLE_KEYMAP" >"$ROOT_MOUNT/etc/vconsole.conf"
chroot "$ROOT_MOUNT" sh -c "id '$USER_NAME' >/dev/null 2>&1 || useradd -m -s /bin/bash '$USER_NAME'"
printf '%s:%s\nroot:%s\n' "$USER_NAME" "$USER_PASSWORD" "$ROOT_PASSWORD" | chroot "$ROOT_MOUNT" chpasswd
chroot "$ROOT_MOUNT" usermod -aG sudo,audio,video,plugdev,netdev "$USER_NAME" 2>/dev/null || true
if [ "$DISPLAY_MANAGER" != "none" ]; then chroot "$ROOT_MOUNT" systemctl enable "$DISPLAY_MANAGER" 2>/dev/null || true; fi
if [ "$NETWORK_BACKEND" = "networkmanager" ]; then chroot "$ROOT_MOUNT" systemctl enable NetworkManager 2>/dev/null || true; fi
if is_enabled "$BLUETOOTH"; then chroot "$ROOT_MOUNT" systemctl enable bluetooth 2>/dev/null || true; fi
if is_enabled "$AUTO_RESIZE"; then
  cat >"$ROOT_MOUNT/etc/systemd/system/debian-usb-growroot.service" <<'EOF'
[Unit]
Description=Grow USB root filesystem on first boot
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/bin/sh -c 'growpart /dev/disk/by-label/DEBIANUSBROOT 2 || true; resize2fs /dev/disk/by-label/DEBIANUSBROOT || true; systemctl disable debian-usb-growroot.service'
[Install]
WantedBy=multi-user.target
EOF
  chroot "$ROOT_MOUNT" systemctl enable debian-usb-growroot.service 2>/dev/null || true
fi
