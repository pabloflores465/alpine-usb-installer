#!/bin/sh
# Configure a Void Linux root filesystem for a bootable USB image.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }
normalize_words() { printf '%s' "${1:-}" | tr ',;:' '   ' | tr '\n\t' '  '; }
has_word() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
PACKAGES=""
append_packages() { for pkg in "$@"; do [ -n "$pkg" ] || continue; case " $PACKAGES " in *" $pkg "*) ;; *) PACKAGES="$PACKAGES $pkg" ;; esac; done; }
safe_token() { case "$2" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$1 contains unsupported characters: $2" ;; esac; }
safe_optional_token() { [ -z "$2" ] && return 0; safe_token "$1" "$2"; }
safe_package_name() { case "$1" in ""|-*|*[!A-Za-z0-9+_.-]*) die "Invalid package name: $1" ;; esac; }
read_secret_value() { eval "file_value=\${$1:-}"; eval "direct_value=\${$2:-}"; if [ -n "$file_value" ]; then [ -f "$file_value" ] || die "Secret file not found: $file_value"; cat "$file_value"; elif [ -n "$direct_value" ]; then printf '%s' "$direct_value"; else printf '%s' "$3"; fi; }

USER_NAME="${LEDIT_USB_USER:-void}"
USER_PASSWORD="$(read_secret_value LEDIT_USB_PASSWORD_FILE LEDIT_USB_PASSWORD void)"
ROOT_PASSWORD="$(read_secret_value LEDIT_USB_ROOT_PASSWORD_FILE LEDIT_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${LEDIT_USB_HOSTNAME:-ledit-void}"
TIMEZONE="${LEDIT_USB_TIMEZONE:-UTC}"
LOCALE="${LEDIT_USB_LOCALE:-en_US.UTF-8}"
LANGUAGE_VALUE="${LEDIT_USB_LANGUAGE:-${LOCALE%%.*}:en}"
CONSOLE_KEYMAP="${LEDIT_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${LEDIT_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${LEDIT_USB_XKB_VARIANT:-}"
XKB_MODEL="${LEDIT_USB_XKB_MODEL:-pc105}"
DESKTOP="$(lower "${LEDIT_USB_DESKTOP:-xfce}")"
TILING_WMS="$(normalize_words "${LEDIT_USB_TILING_WMS:-}")"
DEFAULT_SESSION="$(lower "${LEDIT_USB_DEFAULT_SESSION:-auto}")"
DISPLAY_MANAGER="$(lower "${LEDIT_USB_DISPLAY_MANAGER:-auto}")"
NETWORK_BACKEND="$(lower "${LEDIT_USB_NETWORK:-networkmanager}")"
WIFI="${LEDIT_USB_WIFI:-1}"
BLUETOOTH="${LEDIT_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${LEDIT_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${LEDIT_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${LEDIT_USB_FIRMWARE:-full}")"
LEGACY_X11_DRIVERS="${LEDIT_USB_LEGACY_X11_DRIVERS:-1}"
PROFILE="${LEDIT_USB_PROFILE:-compatibility}"
BOOTLOADER="$(lower "${LEDIT_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${LEDIT_USB_KERNEL_FLAVOR:-lts}")"
BOOT_TIMEOUT="${LEDIT_USB_BOOT_TIMEOUT:-3}"
SYSTEMD_BOOT_CONSOLE_MODE="${LEDIT_USB_SYSTEMD_BOOT_CONSOLE_MODE:-max}"
AUTO_RESIZE="${LEDIT_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${LEDIT_USB_EXTRA_PACKAGES:-${VOID_USB_EXTRA_PACKAGES:-}}"
DRY_RUN="${LEDIT_USB_DRY_RUN:-0}"

case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token Timezone "$TIMEZONE"; safe_token Locale "$LOCALE"; safe_token Language "$LANGUAGE_VALUE"; safe_token "Console keymap" "$CONSOLE_KEYMAP"; safe_token "XKB layout" "$XKB_LAYOUT"; safe_optional_token "XKB variant" "$XKB_VARIANT"; safe_token "XKB model" "$XKB_MODEL"
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
[ "$BOOTLOADER" = systemdboot ] && BOOTLOADER=systemd-boot
case "$KERNEL_FLAVOR" in lts|stable) ;; *) die "Unsupported kernel flavor: $KERNEL_FLAVOR" ;; esac
VALID_WMS="i3 sway hyprland awesome bspwm openbox labwc"
for wm in $TILING_WMS; do has_word "$wm" "$VALID_WMS" || die "Unsupported window manager: $wm"; done
if [ "$DEFAULT_SESSION" = auto ]; then if [ "$DESKTOP" != none ]; then DEFAULT_SESSION="$DESKTOP"; else set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; fi; fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac
if [ "$DISPLAY_MANAGER" = auto ]; then case "$DESKTOP" in gnome) DISPLAY_MANAGER=gdm ;; plasma|lxqt) DISPLAY_MANAGER=sddm ;; xfce|mate) DISPLAY_MANAGER=lightdm ;; none) if [ -n "$TILING_WMS" ]; then DISPLAY_MANAGER=greetd; else DISPLAY_MANAGER=none; fi ;; esac; fi
GRAPHICAL=0; if [ "$DESKTOP" != none ] || [ -n "$TILING_WMS" ]; then GRAPHICAL=1; fi; case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm) GRAPHICAL=1 ;; esac

append_packages base-system shadow sudo bash zsh curl wget git nano vim htop less e2fsprogs dosfstools util-linux kbd tzdata glibc-locales dbus elogind polkit seatd chrony upower noto-fonts-ttf noto-fonts-emoji terminus-font
is_enabled "$AUTO_RESIZE" && append_packages cloud-utils
[ "$FIRMWARE" = full ] && append_packages linux-firmware
case "$KERNEL_FLAVOR" in lts) append_packages linux6.6 ;; stable) append_packages linux ;; esac
case "$BOOTLOADER" in grub) append_packages grub-x86_64-efi efibootmgr ;; systemd-boot) append_packages gummiboot-efistub efibootmgr ;; esac
if [ "$GRAPHICAL" = 1 ]; then append_packages xorg xorg-input-drivers mesa-dri libinput xrandr xdg-utils xkeyboard-config; is_enabled "$LEGACY_X11_DRIVERS" && append_packages xf86-video-amdgpu xf86-video-ati xf86-video-intel xf86-video-nouveau xf86-video-vesa xf86-video-fbdev; fi
case "$DESKTOP" in xfce) append_packages xfce4 xfce4-terminal xfce4-screensaver xfce4-power-manager gvfs udisks2 ;; gnome) append_packages gnome gnome-terminal ;; plasma) append_packages plasma-desktop konsole dolphin ;; mate) append_packages mate mate-terminal gvfs udisks2 ;; lxqt) append_packages lxqt qterminal pcmanfm-qt gvfs udisks2 ;; none) ;; esac
for wm in $TILING_WMS; do case "$wm" in i3) append_packages i3 i3status i3lock dmenu xterm feh picom ;; sway) append_packages sway swaybg swayidle swaylock foot Waybar mako grim slurp xorg-server-xwayland xdg-desktop-portal-wlr ;; hyprland) append_packages Hyprland foot Waybar mako xorg-server-xwayland xdg-desktop-portal ;; awesome) append_packages awesome xterm rofi picom ;; bspwm) append_packages bspwm sxhkd polybar xterm dmenu feh picom ;; openbox) append_packages openbox tint2 xterm dmenu feh picom ;; labwc) append_packages labwc foot swaybg Waybar mako xdg-desktop-portal-wlr ;; esac; done
case "$DISPLAY_MANAGER" in lightdm) append_packages lightdm lightdm-gtk3-greeter accountsservice ;; sddm) append_packages sddm accountsservice ;; gdm) append_packages gdm accountsservice ;; lxdm) append_packages lxdm ;; greetd) append_packages greetd tuigreet ;; none) ;; esac
if [ "$NETWORK_BACKEND" = networkmanager ]; then append_packages NetworkManager; is_enabled "$WIFI" && append_packages wpa_supplicant wireless-regdb; [ "$GRAPHICAL" = 1 ] && append_packages network-manager-applet gnome-keyring; fi
case "$AUDIO" in pipewire) append_packages pipewire wireplumber wireplumber-elogind alsa-pipewire alsa-utils pwvucontrol ;; alsa) append_packages alsa-utils ;; none) ;; esac
is_enabled "$BLUETOOTH" && { append_packages bluez; [ "$GRAPHICAL" = 1 ] && append_packages blueman; }
case "$BROWSER" in firefox-esr) append_packages firefox-esr ;; firefox) append_packages firefox ;; chromium) append_packages chromium ;; none) ;; esac
for pkg in $EXTRA_PACKAGES; do safe_package_name "$pkg"; append_packages "$pkg"; done

if [ "$DRY_RUN" = 1 ]; then cat <<EOF
DRY RUN OK
 distro=void
 desktop=$DESKTOP
 tiling_wms=$TILING_WMS
 default_session=$DEFAULT_SESSION
 display_manager=$DISPLAY_MANAGER
 network=$NETWORK_BACKEND wifi=$WIFI bluetooth=$BLUETOOTH audio=$AUDIO
 bootloader=$BOOTLOADER kernel=$KERNEL_FLAVOR firmware=$FIRMWARE auto_resize=$AUTO_RESIZE legacy_x11_drivers=$LEGACY_X11_DRIVERS systemd_boot_console_mode=$SYSTEMD_BOOT_CONSOLE_MODE
 locale=$LOCALE keyboard=$XKB_LAYOUT console_keymap=$CONSOLE_KEYMAP
 packages:$PACKAGES
EOF
exit 0; fi

if is_enabled "${LEDIT_USB_SKIP_PACKAGE_INSTALL:-${VOID_USB_SKIP_PACKAGE_INSTALL:-0}}"; then
  echo "Skipping package install; packages were preinstalled by build-void-usb.sh"
else
  command -v xbps-install >/dev/null 2>&1 || die "xbps-install is required inside the Void target root"
  # shellcheck disable=SC2086
  xbps-install -Sy $PACKAGES
fi
printf '%s\n' "$HOSTNAME" > /etc/hostname
printf 'LANG=%s\nLANGUAGE=%s\nLC_MESSAGES=%s\n' "$LOCALE" "$LANGUAGE_VALUE" "$LOCALE" > /etc/locale.conf
printf '%s\n' "$TIMEZONE" > /etc/timezone
ln -sf "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime 2>/dev/null || true
printf 'KEYMAP=%s\n' "$CONSOLE_KEYMAP" > /etc/vconsole.conf
printf 'root:%s\n%s:%s\n' "$ROOT_PASSWORD" "$USER_NAME" "$USER_PASSWORD" | chpasswd
for group in wheel audio video input storage network bluetooth; do
  getent group "$group" >/dev/null 2>&1 || groupadd -r "$group"
done
id "$USER_NAME" >/dev/null 2>&1 || useradd -m -G wheel,audio,video,input,storage,network,bluetooth -s /bin/bash "$USER_NAME"
printf 'permit persist :wheel\n' > /etc/doas.conf 2>/dev/null || true
mkdir -p /etc/sv
mkdir -p /var/service 2>/dev/null || { rm -f /var/service; mkdir -p /var/service; }
for svc in dbus elogind polkitd chronyd NetworkManager bluetoothd lightdm sddm gdm lxdm greetd; do [ -d "/etc/sv/$svc" ] && ln -snf "/etc/sv/$svc" "/var/service/$svc"; done
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<EOF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "$XKB_LAYOUT"
    Option "XkbModel" "$XKB_MODEL"
    Option "XkbVariant" "$XKB_VARIANT"
EndSection
EOF
cat > /usr/local/bin/linux-usb-session <<EOF
#!/bin/sh
session="\${1:-$DEFAULT_SESSION}"
case "\$session" in
  xfce) exec startxfce4 ;; gnome) exec gnome-session ;; plasma) exec startplasma-x11 ;; mate) exec mate-session ;; lxqt) exec startlxqt ;; i3) exec i3 ;; sway) exec sway ;; hyprland) exec Hyprland ;; awesome) exec awesome ;; bspwm) exec bspwm ;; openbox) exec openbox-session ;; labwc) exec labwc ;; *) exec /bin/sh -l ;;
esac
EOF
chmod +x /usr/local/bin/linux-usb-session
