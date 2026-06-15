#!/bin/sh
# Runs inside target Alpine image/chroot via alpine-make-vm-image.
# The script is intentionally configurable through ALPINE_USB_* variables so
# the Qt installer can build more than the original fixed XFCE profile.
set -eu

# ---- Helpers -------------------------------------------------------------
die() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARN: $*" >&2; }

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

is_enabled() {
  case "$(lower "${1:-0}")" in
    1|yes|true|on|enabled) return 0 ;;
    *) return 1 ;;
  esac
}

normalize_words() {
  printf '%s' "${1:-}" | tr ',;:' '   ' | tr '\n\t' '  '
}

has_word() {
  needle="$1"
  words=" $2 "
  case "$words" in *" $needle "*) return 0 ;; *) return 1 ;; esac
}

PACKAGES=""
append_packages() {
  for pkg in "$@"; do
    [ -n "$pkg" ] || continue
    case " $PACKAGES " in
      *" $pkg "*) ;;
      *) PACKAGES="$PACKAGES $pkg" ;;
    esac
  done
}

shell_quote() {
  # single-quote a value for generated shell scripts
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

safe_token() {
  name="$1"; value="$2"
  case "$value" in
    *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;;
  esac
}

safe_optional_token() {
  name="$1"; value="$2"
  [ -z "$value" ] && return 0
  safe_token "$name" "$value"
}

safe_package_name() {
  pkg="$1"
  case "$pkg" in
    ""|-*|*[!A-Za-z0-9+_.-]*) die "Invalid package name: $pkg" ;;
  esac
}

read_secret_value() {
  file_var="$1"
  value_var="$2"
  default_value="$3"
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

# ---- Input configuration -------------------------------------------------
USER_NAME="${ALPINE_USB_USER:-alpine}"
USER_PASSWORD="$(read_secret_value ALPINE_USB_PASSWORD_FILE ALPINE_USB_PASSWORD alpine)"
ROOT_PASSWORD="$(read_secret_value ALPINE_USB_ROOT_PASSWORD_FILE ALPINE_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${ALPINE_USB_HOSTNAME:-alpine-usb}"
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
BOOTLOADER="$(lower "${ALPINE_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${ALPINE_USB_KERNEL_FLAVOR:-lts}")"
ROOTFS="$(lower "${ALPINE_USB_ROOTFS:-ext4}")"
BOOT_TIMEOUT="${ALPINE_USB_BOOT_TIMEOUT:-3}"
INITFS_FEATURES="${ALPINE_USB_INITFS_FEATURES:-ata base ext4 kms mmc nvme scsi usb virtio}"
SYSTEMD_BOOT_CONSOLE_MODE="${ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE:-max}"
AUTO_RESIZE="${ALPINE_USB_AUTO_RESIZE:-1}"
EXTRA_PACKAGES="${ALPINE_USB_EXTRA_PACKAGES:-}"
DRY_RUN="${ALPINE_USB_DRY_RUN:-0}"

# ---- Validation and auto resolution --------------------------------------
case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token "Timezone" "$TIMEZONE"
safe_token "Locale" "$LOCALE"
safe_token "Language" "$LANGUAGE_VALUE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"
safe_token "XKB layout" "$XKB_LAYOUT"
safe_optional_token "XKB variant" "$XKB_VARIANT"
safe_token "XKB model" "$XKB_MODEL"
case "$BOOT_TIMEOUT" in *[!0-9]*|"") die "Boot timeout must be a number" ;; esac
case "$SYSTEMD_BOOT_CONSOLE_MODE" in keep|auto|max|[0-9]|[0-9][0-9]) ;; *) die "Unsupported systemd-boot console mode: $SYSTEMD_BOOT_CONSOLE_MODE" ;; esac
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac

case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt|none) ;; *) die "Unsupported desktop: $DESKTOP" ;; esac
case "$DISPLAY_MANAGER" in auto|lightdm|sddm|gdm|lxdm|greetd|none) ;; *) die "Unsupported display manager: $DISPLAY_MANAGER" ;; esac
case "$NETWORK_BACKEND" in networkmanager|none) ;; *) die "Unsupported network backend: $NETWORK_BACKEND" ;; esac
case "$AUDIO" in pipewire|alsa|none) ;; *) die "Unsupported audio option: $AUDIO" ;; esac
case "$BROWSER" in firefox-esr|firefox|chromium|none) ;; *) die "Unsupported browser: $BROWSER" ;; esac
case "$FIRMWARE" in full|none) ;; *) die "Unsupported firmware option: $FIRMWARE" ;; esac
case "$BOOTLOADER" in grub|systemd-boot|systemdboot) ;; *) die "Unsupported bootloader: $BOOTLOADER" ;; esac
[ "$BOOTLOADER" = "systemdboot" ] && BOOTLOADER="systemd-boot"
case "$KERNEL_FLAVOR" in lts|stable) ;; *) die "Unsupported kernel flavor: $KERNEL_FLAVOR" ;; esac
case "$ROOTFS" in ext4) ;; *) die "Unsupported root filesystem in this installer: $ROOTFS" ;; esac

VALID_WMS="i3 sway hyprland awesome bspwm openbox labwc"
for wm in $TILING_WMS; do
  has_word "$wm" "$VALID_WMS" || die "Unsupported window manager: $wm"
done

if [ "$DEFAULT_SESSION" = "auto" ]; then
  if [ "$DESKTOP" != "none" ]; then
    DEFAULT_SESSION="$DESKTOP"
  else
    # shellcheck disable=SC2086 # TILING_WMS is normalized to space-separated identifiers.
    set -- $TILING_WMS
    DEFAULT_SESSION="${1:-shell}"
  fi
fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|hyprland|awesome|bspwm|openbox|labwc|shell) ;;
  *) die "Unsupported default session: $DEFAULT_SESSION" ;;
esac

if [ "$DISPLAY_MANAGER" = "auto" ]; then
  case "$DESKTOP" in
    gnome) DISPLAY_MANAGER="gdm" ;;
    plasma|lxqt) DISPLAY_MANAGER="sddm" ;;
    xfce|mate) DISPLAY_MANAGER="lightdm" ;;
    none)
      if [ -n "$TILING_WMS" ]; then DISPLAY_MANAGER="greetd"; else DISPLAY_MANAGER="none"; fi ;;
  esac
fi

case "$DEFAULT_SESSION" in
  shell)
    case "$DISPLAY_MANAGER" in none|greetd) ;; *) die "A graphical display manager needs a desktop or WM session" ;; esac ;;
  sway|hyprland|labwc)
    case "$DISPLAY_MANAGER" in lightdm|lxdm) die "Wayland sessions ($DEFAULT_SESSION) require greetd, SDDM, GDM or no display manager" ;; esac ;;
esac

GRAPHICAL=0
if [ "$DESKTOP" != "none" ] || [ -n "$TILING_WMS" ]; then GRAPHICAL=1; fi
case "$DISPLAY_MANAGER" in lightdm|sddm|gdm|lxdm) GRAPHICAL=1 ;; esac

# ---- Package selection ----------------------------------------------------
append_packages \
  alpine-base "linux-$KERNEL_FLAVOR" \
  eudev seatd acpid kbd upower chrony ca-certificates tzdata \
  dbus dbus-x11 elogind polkit-elogind \
  doas sudo bash zsh curl wget git nano vim htop less \
  e2fsprogs dosfstools lsblk blkid util-linux \
  font-noto font-noto-emoji terminus-font

if is_enabled "$AUTO_RESIZE"; then
  append_packages cloud-utils-growpart
fi

if [ "$FIRMWARE" = "full" ]; then
  append_packages linux-firmware
else
  append_packages linux-firmware-none
fi

case "$BOOTLOADER" in
  grub) append_packages grub grub-efi efibootmgr ;;
  systemd-boot) append_packages systemd-boot efibootmgr ;;
esac

if [ "$GRAPHICAL" = "1" ]; then
  append_packages \
    xorg-server xinit setxkbmap xkeyboard-config libinput xf86-input-libinput \
    xf86-video-amdgpu xf86-video-ati xf86-video-intel xf86-video-nouveau \
    xf86-video-vesa xf86-video-fbdev \
    mesa-dri-gallium mesa-egl mesa-gl xrandr xdg-utils
fi

case "$DESKTOP" in
  xfce)
    append_packages xfce4 xfce4-terminal xfce4-screensaver xfce4-power-manager xfce4-notifyd \
      gvfs udisks2 thunar-volman xfce-polkit ;;
  gnome)
    append_packages gnome gnome-terminal ;;
  plasma)
    append_packages plasma-desktop-meta konsole dolphin ;;
  mate)
    append_packages mate-desktop-environment mate-terminal gvfs udisks2 ;;
  lxqt)
    append_packages lxqt-desktop qterminal pcmanfm-qt gvfs udisks2 ;;
  none) ;;
esac

for wm in $TILING_WMS; do
  case "$wm" in
    i3) append_packages i3wm i3status i3lock dmenu xterm feh picom polkit-gnome ;;
    sway) append_packages sway swaybg swayidle swaylock foot waybar mako grim slurp xwayland xdg-desktop-portal xdg-desktop-portal-wlr polkit-gnome ;;
    hyprland) append_packages hyprland foot waybar mako xwayland xdg-desktop-portal polkit-gnome ;;
    awesome) append_packages awesome xterm rofi picom polkit-gnome ;;
    bspwm) append_packages bspwm sxhkd polybar xterm dmenu feh picom polkit-gnome ;;
    openbox) append_packages openbox tint2 xterm dmenu feh picom polkit-gnome ;;
    labwc) append_packages labwc foot swaybg waybar mako xdg-desktop-portal xdg-desktop-portal-wlr polkit-gnome ;;
  esac
done

case "$DISPLAY_MANAGER" in
  lightdm) append_packages lightdm lightdm-gtk-greeter lightdm-openrc accountsservice ;;
  sddm) append_packages sddm sddm-openrc accountsservice ;;
  gdm) append_packages gdm gdm-openrc accountsservice ;;
  lxdm) append_packages lxdm lxdm-openrc ;;
  greetd) append_packages greetd greetd-openrc greetd-tuigreet ;;
  none) ;;
esac

if [ "$NETWORK_BACKEND" = "networkmanager" ]; then
  append_packages networkmanager networkmanager-cli networkmanager-tui
  if is_enabled "$WIFI"; then
    append_packages networkmanager-wifi wireless-regdb wpa_supplicant
  fi
  if [ "$GRAPHICAL" = "1" ]; then
    append_packages network-manager-applet gnome-keyring
  fi
fi

case "$AUDIO" in
  pipewire) append_packages pipewire wireplumber pipewire-pulse alsa-utils alsa-plugins-pulse pavucontrol ;;
  alsa) append_packages alsa-utils ;;
  none) ;;
esac

if is_enabled "$BLUETOOTH"; then
  # Use obexd-enhanced instead of bluez-obexd. GNOME Bluetooth requires
  # obexd-enhanced and it conflicts with bluez-obexd; obexd-enhanced provides
  # the same obexd service plus PBAP support, so it is the compatible choice
  # across GNOME, XFCE, Plasma, MATE, LXQt and WM-only profiles.
  append_packages bluez bluez-openrc bluez-firmware bluez-btmgmt obexd-enhanced
  [ "$GRAPHICAL" = "1" ] && append_packages blueman
fi

case "$BROWSER" in
  firefox-esr) append_packages firefox-esr ;;
  firefox) append_packages firefox ;;
  chromium) append_packages chromium ;;
  none) ;;
esac

for pkg in $EXTRA_PACKAGES; do
  safe_package_name "$pkg"
  append_packages "$pkg"
done

if [ "$DRY_RUN" = "1" ]; then
  cat <<EOF
DRY RUN OK
 desktop=$DESKTOP
 tiling_wms=$TILING_WMS
 default_session=$DEFAULT_SESSION
 display_manager=$DISPLAY_MANAGER
 network=$NETWORK_BACKEND wifi=$WIFI bluetooth=$BLUETOOTH audio=$AUDIO
 bootloader=$BOOTLOADER kernel=$KERNEL_FLAVOR firmware=$FIRMWARE rootfs=$ROOTFS auto_resize=$AUTO_RESIZE systemd_boot_console_mode=$SYSTEMD_BOOT_CONSOLE_MODE
 locale=$LOCALE keyboard=$XKB_LAYOUT console_keymap=$CONSOLE_KEYMAP
 packages:$PACKAGES
EOF
  exit 0
fi

# ---- Base system ----------------------------------------------------------
apk update
apk upgrade --available

# Install polkit-elogind before desktop packages. This prevents apk from
# selecting the non-elogind polkit provider when a desktop/polkit-agent package
# depends on "polkit". This fixes the previous xfce-polkit/polkit conflict.
apk add alpine-base "linux-$KERNEL_FLAVOR" dbus dbus-x11 elogind polkit-elogind ca-certificates tzdata
if [ "$FIRMWARE" = "full" ]; then
  apk del linux-firmware-none >/dev/null 2>&1 || true
fi
# shellcheck disable=SC2086 # PACKAGES is a generated package list.
apk add $PACKAGES

# ---- Locale, timezone and keyboard ---------------------------------------
mkdir -p /etc/profile.d /etc/X11/xorg.conf.d
cat > /etc/profile.d/00-lang.sh <<EOF
export LANG=$LOCALE
export LANGUAGE=$LANGUAGE_VALUE
export LC_MESSAGES=$LOCALE
EOF
chmod +x /etc/profile.d/00-lang.sh
cat > /etc/environment <<EOF
LANG=$LOCALE
LANGUAGE=$LANGUAGE_VALUE
LC_MESSAGES=$LOCALE
EOF
cat > /etc/locale.conf <<EOF
LANG=$LOCALE
EOF

if [ -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
  cp "/usr/share/zoneinfo/$TIMEZONE" /etc/localtime
  echo "$TIMEZONE" > /etc/timezone
else
  warn "Timezone not found in tzdata: $TIMEZONE; keeping UTC"
fi

cat > /etc/conf.d/loadkeys <<EOF
keymap="$CONSOLE_KEYMAP"
windowkeys="YES"
extended_keymaps=""
dumpkeys_charset=""
fix_euro="NO"
unicode="YES"
EOF
# Compatibility for older Alpine/OpenRC setups that used /etc/conf.d/keymaps.
cat > /etc/conf.d/keymaps <<EOF
KEYMAP="$CONSOLE_KEYMAP"
WINDOWKEYS="YES"
EXTENDED_KEYMAPS=""
DUMPKEYS_CHARSET=""
FIX_EURO="NO"
UNICODE="YES"
EOF

cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<EOF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "$XKB_LAYOUT"
    Option "XkbModel" "$XKB_MODEL"
    Option "XkbVariant" "$XKB_VARIANT"
EndSection
EOF

cat > /etc/X11/xorg.conf.d/30-touchpad.conf <<'EOF'
Section "InputClass"
    Identifier "libinput touchpad defaults"
    MatchIsTouchpad "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "NaturalScrolling" "false"
EndSection
EOF

q_layout=$(shell_quote "$XKB_LAYOUT")
q_variant=$(shell_quote "$XKB_VARIANT")
cat > /usr/local/bin/alpine-usb-setxkbmap <<EOF
#!/bin/sh
layout=$q_layout
variant=$q_variant
if [ -n "\$variant" ]; then
  /usr/bin/setxkbmap -layout "\$layout" -variant "\$variant" 2>/dev/null || true
else
  /usr/bin/setxkbmap "\$layout" 2>/dev/null || true
fi
EOF
chmod +x /usr/local/bin/alpine-usb-setxkbmap

# ---- Session launcher and display managers -------------------------------
cat > /usr/local/bin/alpine-usb-session <<EOF
#!/bin/sh
session="\${1:-$DEFAULT_SESSION}"
export LANG=${LOCALE}
export LANGUAGE=${LANGUAGE_VALUE}
export LC_MESSAGES=${LOCALE}
/usr/local/bin/alpine-usb-setxkbmap 2>/dev/null || true
run_dbus() {
  if command -v dbus-run-session >/dev/null 2>&1; then
    exec dbus-run-session -- "\$@"
  fi
  exec "\$@"
}
start_x_if_needed() {
  if [ -z "\${DISPLAY:-}" ] && [ -z "\${WAYLAND_DISPLAY:-}" ] && command -v startx >/dev/null 2>&1; then
    exec startx /usr/local/bin/alpine-usb-session "\$session" --
  fi
}
case "\$session" in
  xfce) start_x_if_needed; exec startxfce4 ;;
  gnome) run_dbus gnome-session ;;
  plasma)
    if [ -n "\${DISPLAY:-}" ] && command -v startplasma-x11 >/dev/null 2>&1; then exec startplasma-x11; fi
    exec startplasma-wayland ;;
  mate) start_x_if_needed; exec mate-session ;;
  lxqt) start_x_if_needed; exec startlxqt ;;
  i3) start_x_if_needed; exec i3 ;;
  sway) run_dbus sway ;;
  hyprland) run_dbus Hyprland ;;
  awesome) start_x_if_needed; exec awesome ;;
  bspwm) start_x_if_needed; exec bspwm ;;
  openbox) start_x_if_needed; exec openbox-session ;;
  labwc) run_dbus labwc ;;
  shell) exec /bin/sh -l ;;
  *) exec /bin/sh -l ;;
esac
EOF
chmod +x /usr/local/bin/alpine-usb-session

if [ "$GRAPHICAL" = "1" ]; then
  mkdir -p /usr/share/xsessions /usr/share/wayland-sessions
  cat > /usr/share/xsessions/alpine-usb.desktop <<EOF
[Desktop Entry]
Name=Alpine USB Default ($DEFAULT_SESSION)
Comment=Default session selected by Alpine USB Installer
Exec=/usr/local/bin/alpine-usb-session
Type=Application
DesktopNames=AlpineUSB
EOF
  cat > /usr/share/wayland-sessions/alpine-usb.desktop <<EOF
[Desktop Entry]
Name=Alpine USB Default ($DEFAULT_SESSION)
Comment=Default session selected by Alpine USB Installer
Exec=/usr/local/bin/alpine-usb-session
Type=Application
DesktopNames=AlpineUSB
EOF
fi

case "$DISPLAY_MANAGER" in
  lightdm)
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat > /etc/lightdm/lightdm.conf.d/50-alpine-usb.conf <<EOF
[Seat:*]
greeter-session=lightdm-gtk-greeter
user-session=alpine-usb
allow-guest=false
display-setup-script=/usr/local/bin/alpine-usb-setxkbmap
greeter-setup-script=/usr/local/bin/alpine-usb-setxkbmap
EOF
    cat > /etc/lightdm/lightdm-gtk-greeter.conf <<'EOF'
[greeter]
indicators=~host;~spacer;~clock;~spacer;~session;~language;~a11y;~power
clock-format=%a, %b %d  %H:%M
EOF
    ;;
  sddm)
    mkdir -p /etc/sddm.conf.d
    cat > /etc/sddm.conf.d/10-alpine-usb.conf <<'EOF'
[General]
HaltCommand=/sbin/poweroff
RebootCommand=/sbin/reboot
InputMethod=

[Users]
MinimumUid=1000
MaximumUid=65000
EOF
    ;;
  lxdm)
    if [ -f /etc/lxdm/lxdm.conf ]; then
      sed -i 's|^session=.*|session=/usr/local/bin/alpine-usb-session|' /etc/lxdm/lxdm.conf || true
    fi
    ;;
  greetd)
    mkdir -p /etc/greetd
    cat > /etc/greetd/config.toml <<EOF
[terminal]
vt = 7

[default_session]
command = "tuigreet --time --remember --asterisks --cmd /usr/local/bin/alpine-usb-session"
user = "greetd"
EOF
    ;;
  gdm|none) ;;
esac

# ---- User ----------------------------------------------------------------
if ! getent group "$USER_NAME" >/dev/null 2>&1; then
  addgroup "$USER_NAME"
fi
if ! id "$USER_NAME" >/dev/null 2>&1; then
  adduser -D -s /bin/bash -G "$USER_NAME" "$USER_NAME"
fi
printf '%s:%s\n' "$USER_NAME" "$USER_PASSWORD" | chpasswd
printf 'root:%s\n' "$ROOT_PASSWORD" | chpasswd
for group in wheel audio video input plugdev netdev seat tty lp scanner; do
  addgroup "$USER_NAME" "$group" >/dev/null 2>&1 || true
done

mkdir -p /etc/doas.d
cat > /etc/doas.d/doas.conf <<'EOF'
permit persist :wheel
EOF
chmod 600 /etc/doas.d/doas.conf

echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
chmod 440 /etc/sudoers.d/wheel

mkdir -p /etc/X11
cat > /etc/X11/Xwrapper.config <<'EOF'
allowed_users=console
needs_root_rights=auto
EOF

cat > "/home/$USER_NAME/.dmrc" <<EOF
[Desktop]
Session=alpine-usb
Language=$LOCALE
EOF
cat > "/home/$USER_NAME/.xinitrc" <<'EOF'
#!/bin/sh
exec /usr/local/bin/alpine-usb-session
EOF
chmod +x "/home/$USER_NAME/.xinitrc"
chown "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.dmrc" "/home/$USER_NAME/.xinitrc"

# ---- Desktop applets and polkit agent ------------------------------------
mkdir -p /usr/local/bin /etc/xdg/autostart
cat > /usr/local/bin/alpine-usb-polkit-agent <<'EOF'
#!/bin/sh
# Avoid duplicate polkit agents when a DE autostarts its own agent.
if command -v pgrep >/dev/null 2>&1 && pgrep -u "$(id -u)" -f 'polkit.*authentication|xfce-polkit|lxqt-policykit|mate-polkit' >/dev/null 2>&1; then
  exit 0
fi
for agent in \
  /usr/lib/xfce4/xfce-polkit \
  /usr/libexec/xfce-polkit \
  /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 \
  /usr/libexec/polkit-gnome-authentication-agent-1 \
  /usr/lib/mate-polkit/polkit-mate-authentication-agent-1 \
  /usr/libexec/polkit-mate-authentication-agent-1 \
  /usr/lib/lxqt-policykit/lxqt-policykit-agent \
  /usr/libexec/lxqt-policykit-agent \
  /usr/lib/libexec/polkit-kde-authentication-agent-1 \
  /usr/lib/polkit-kde-authentication-agent-1
 do
  [ -x "$agent" ] && exec "$agent"
done
command -v lxqt-policykit-agent >/dev/null 2>&1 && exec lxqt-policykit-agent
command -v polkit-gnome-authentication-agent-1 >/dev/null 2>&1 && exec polkit-gnome-authentication-agent-1
exit 0
EOF
chmod +x /usr/local/bin/alpine-usb-polkit-agent
cat > /etc/xdg/autostart/alpine-usb-polkit-agent.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=PolicyKit Authentication Agent
Exec=/usr/local/bin/alpine-usb-polkit-agent
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF

if [ "$NETWORK_BACKEND" = "networkmanager" ] && [ "$GRAPHICAL" = "1" ]; then
  cat > /usr/local/bin/alpine-usb-nm-applet <<'EOF'
#!/bin/sh
command -v nm-applet >/dev/null 2>&1 || exit 0
if command -v pgrep >/dev/null 2>&1 && pgrep -u "$(id -u)" -x nm-applet >/dev/null 2>&1; then exit 0; fi
exec nm-applet
EOF
  chmod +x /usr/local/bin/alpine-usb-nm-applet
  cat > /etc/xdg/autostart/alpine-usb-nm-applet.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Network Manager Applet
Exec=/usr/local/bin/alpine-usb-nm-applet
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
fi

if [ "$AUDIO" = "pipewire" ] && [ "$GRAPHICAL" = "1" ]; then
  cat > /usr/local/bin/alpine-usb-pipewire-session <<'EOF'
#!/bin/sh
# Start the desktop audio session explicitly. On Alpine/OpenRC there is no
# systemd --user manager, so do not rely on systemd user units for PipeWire.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true

start_once() {
  name="$1"; shift
  if command -v pgrep >/dev/null 2>&1 && pgrep -u "$(id -u)" -x "$name" >/dev/null 2>&1; then
    return 0
  fi
  command -v "$name" >/dev/null 2>&1 || return 0
  "$@" >/tmp/alpine-usb-"$name".log 2>&1 &
}

start_once pipewire pipewire
sleep 1
start_once wireplumber wireplumber
sleep 1
start_once pipewire-pulse pipewire-pulse
EOF
  chmod +x /usr/local/bin/alpine-usb-pipewire-session
  cat > /etc/xdg/autostart/alpine-usb-pipewire-session.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=PipeWire audio session
Exec=/usr/local/bin/alpine-usb-pipewire-session
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
fi

if is_enabled "$BLUETOOTH" && [ "$GRAPHICAL" = "1" ]; then
  cat > /usr/local/bin/alpine-usb-blueman-applet <<'EOF'
#!/bin/sh
command -v blueman-applet >/dev/null 2>&1 || exit 0
if command -v pgrep >/dev/null 2>&1 && pgrep -u "$(id -u)" -x blueman-applet >/dev/null 2>&1; then exit 0; fi
exec blueman-applet
EOF
  chmod +x /usr/local/bin/alpine-usb-blueman-applet
  cat > /etc/xdg/autostart/alpine-usb-blueman-applet.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Bluetooth Applet
Exec=/usr/local/bin/alpine-usb-blueman-applet
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
fi

# ---- PolicyKit rules ------------------------------------------------------
mkdir -p /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/49-alpine-usb-desktop.rules <<'EOF'
polkit.addRule(function(action, subject) {
    var powerActions = [
        "org.freedesktop.login1.power-off",
        "org.freedesktop.login1.power-off-multiple-sessions",
        "org.freedesktop.login1.reboot",
        "org.freedesktop.login1.reboot-multiple-sessions",
        "org.freedesktop.login1.suspend",
        "org.freedesktop.login1.suspend-multiple-sessions",
        "org.freedesktop.login1.hibernate",
        "org.freedesktop.login1.hibernate-multiple-sessions"
    ];
    if (powerActions.indexOf(action.id) >= 0 && subject.local && subject.active && (subject.isInGroup("wheel") || subject.user == "lightdm" || subject.user == "sddm" || subject.user == "gdm" || subject.user == "greetd")) {
        return polkit.Result.YES;
    }
    if (action.id.indexOf("org.freedesktop.NetworkManager.") === 0 && subject.local && subject.active && (subject.isInGroup("netdev") || subject.isInGroup("wheel"))) {
        return polkit.Result.YES;
    }
    if (action.id.indexOf("org.bluez.") === 0 && subject.local && subject.active && subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
EOF

mkdir -p /etc/elogind/logind.conf.d
cat > /etc/elogind/logind.conf.d/10-alpine-usb.conf <<'EOF'
[Login]
HandlePowerKey=poweroff
HandleRebootKey=reboot
HandleSuspendKey=suspend
HandleHibernateKey=hibernate
HandleLidSwitch=suspend
KillUserProcesses=no
IdleAction=ignore
EOF

# ---- Expand root filesystem to target USB size ---------------------------
if is_enabled "$AUTO_RESIZE"; then
  mkdir -p /usr/local/sbin /etc/init.d /var/lib
  cat > /usr/local/sbin/alpine-usb-grow-root <<'EOF'
#!/bin/sh
set -eu

marker=/var/lib/alpine-usb-grow-root.done
[ -e "$marker" ] && exit 0

resolve_root_device() {
  src="$1"
  if [ -n "$src" ] && [ "$src" != "/dev/root" ] && [ -b "$src" ]; then
    readlink -f "$src"
    return 0
  fi

  root_arg="$(tr ' ' '\n' < /proc/cmdline | sed -n 's/^root=//p' | tail -n 1)"
  case "$root_arg" in
    UUID=*) blkid -U "${root_arg#UUID=}" ;;
    LABEL=*) blkid -L "${root_arg#LABEL=}" ;;
    /dev/*) readlink -f "$root_arg" ;;
    *) return 1 ;;
  esac
}

root_src="$(findmnt -n -o SOURCE / 2>/dev/null || true)"
rootdev="$(resolve_root_device "$root_src" 2>/dev/null || true)"
if [ -z "$rootdev" ] || [ ! -b "$rootdev" ]; then
  echo "Could not resolve root block device from '$root_src'" >&2
  exit 1
fi

pkname="$(lsblk -no PKNAME "$rootdev" 2>/dev/null | head -n 1 | tr -d '[:space:]')"
partnum="$(lsblk -no PARTN "$rootdev" 2>/dev/null | head -n 1 | tr -d '[:space:]')"

if [ -z "$pkname" ] || [ -z "$partnum" ]; then
  case "$rootdev" in
    /dev/nvme*n*p[0-9]*|/dev/mmcblk*p[0-9]*)
      disk="$(printf '%s\n' "$rootdev" | sed 's/p[0-9][0-9]*$//')"
      partnum="$(printf '%s\n' "$rootdev" | sed 's/^.*p//')"
      ;;
    /dev/*[0-9])
      disk="$(printf '%s\n' "$rootdev" | sed 's/[0-9][0-9]*$//')"
      partnum="$(printf '%s\n' "$rootdev" | sed 's/^.*[^0-9]//')"
      ;;
    *)
      echo "Root device '$rootdev' is not a partition; nothing to grow."
      touch "$marker"
      exit 0
      ;;
  esac
else
  disk="/dev/$pkname"
fi

if [ ! -b "$disk" ] || [ -z "$partnum" ]; then
  echo "Could not resolve parent disk/partition for root device '$rootdev'" >&2
  exit 1
fi

echo "Growing root partition $disk $partnum ($rootdev) to fill the target USB..."
out="$(growpart "$disk" "$partnum" 2>&1)" && rc=0 || rc=$?
printf '%s\n' "$out"
if [ "$rc" -ne 0 ]; then
  case "$out" in
    *NOCHANGE*|*"cannot be grown"*|*"could only be grown"*) ;;
    *) echo "growpart failed" >&2; exit "$rc" ;;
  esac
fi

partx -u "$disk" 2>/dev/null || true
blockdev --rereadpt "$disk" 2>/dev/null || true
sleep 1
resize2fs "$rootdev"
touch "$marker"
echo "Root filesystem expansion complete."
EOF
  chmod +x /usr/local/sbin/alpine-usb-grow-root

  cat > /etc/init.d/alpine-usb-grow-root <<'EOF'
#!/sbin/openrc-run
description="Grow Alpine USB root partition/filesystem to fill the target USB drive"

depend() {
  need localmount
  after modules udev-settle
  before lightdm sddm gdm lxdm greetd
}

start() {
  if [ -e /var/lib/alpine-usb-grow-root.done ]; then
    ebegin "Alpine USB root filesystem already expanded"
    eend 0
    return 0
  fi
  ebegin "Expanding Alpine USB root filesystem"
  /usr/local/sbin/alpine-usb-grow-root
  eend $?
}
EOF
  chmod +x /etc/init.d/alpine-usb-grow-root
fi

# ---- Services -------------------------------------------------------------
rc-update add devfs sysinit || true
rc-update add dmesg sysinit || true
rc-update del mdev sysinit || true
rc-update add udev sysinit || true
rc-update add udev-trigger sysinit || true
rc-update add udev-settle sysinit || true
rc-update add hwdrivers sysinit || true
rc-update add modules boot || true
rc-update add loadkeys boot || rc-update add keymaps boot || true
rc-update add sysctl boot || true
rc-update add hostname boot || true
rc-update add bootmisc boot || true
rc-update add syslog boot || true
if is_enabled "$AUTO_RESIZE"; then
  rc-update add alpine-usb-grow-root boot || true
fi
rc-update add networking boot || true
rc-update add chronyd default || true
rc-update add dbus default || true
rc-update add elogind default || true
rc-update add polkit default || true
rc-update add seatd default || true
rc-update add acpid default || true
[ "$GRAPHICAL" = "1" ] && rc-update add udisks2 default || true

if [ "$NETWORK_BACKEND" = "networkmanager" ]; then
  is_enabled "$WIFI" && rc-update add wpa_supplicant default || true
  rc-update add networkmanager default || true
  rc-update del networking default || true
else
  rc-update add networking default || true
fi

if is_enabled "$BLUETOOTH"; then
  rc-update add bluetooth default || true
fi

for svc in lightdm sddm gdm lxdm greetd; do
  rc-update del "$svc" default >/dev/null 2>&1 || true
done
case "$DISPLAY_MANAGER" in
  lightdm|sddm|gdm|lxdm|greetd) rc-update add "$DISPLAY_MANAGER" default || true ;;
  none) ;;
esac

# ---- USB-friendly optimizations ------------------------------------------
mkdir -p /etc/sysctl.d /etc/tmpfiles.d
cat > /etc/sysctl.d/99-usb.conf <<'EOF'
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF

cat > /etc/tmpfiles.d/usb-tmpfs.conf <<'EOF'
d /tmp 1777 root root -
d /var/tmp 1777 root root -
d /var/cache/apk 0755 root root -
EOF

rm -rf /var/cache/apk/* || true
sed -i 's/[[:space:]]relatime[[:space:]]/ noatime /' /etc/fstab 2>/dev/null || true
grep -q '^tmpfs /tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab
grep -q '^tmpfs /var/tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /var/tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab

# ---- NetworkManager -------------------------------------------------------
if [ "$NETWORK_BACKEND" = "networkmanager" ]; then
  mkdir -p /etc/NetworkManager/conf.d
  cat > /etc/NetworkManager/conf.d/10-globally-managed-devices.conf <<'EOF'
[keyfile]
unmanaged-devices=none
EOF
  cat > /etc/NetworkManager/conf.d/20-wifi-usb.conf <<'EOF'
[device]
wifi.scan-rand-mac-address=no

[connection]
wifi.powersave=2
EOF
fi

# ---- Desktop and WM defaults ---------------------------------------------
mkdir -p /etc/skel/Desktop /etc/skel/.config
cat > /etc/skel/.xinitrc <<'EOF'
#!/bin/sh
exec /usr/local/bin/alpine-usb-session
EOF
chmod +x /etc/skel/.xinitrc

if [ "$DESKTOP" = "xfce" ]; then
  mkdir -p /etc/xdg/xfce4/xfconf/xfce-perchannel-xml
  cat > /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/keyboard-layout.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<channel name="keyboard-layout" version="1.0">
  <property name="Default" type="empty">
    <property name="XkbDisable" type="bool" value="false"/>
    <property name="XkbLayout" type="string" value="$XKB_LAYOUT"/>
    <property name="XkbVariant" type="string" value="$XKB_VARIANT"/>
  </property>
</channel>
EOF
fi

if has_word i3 "$TILING_WMS"; then
  mkdir -p /etc/skel/.config/i3
  cat > /etc/skel/.config/i3/config <<'EOF'
set $mod Mod4
font pango:Noto Sans 10
exec --no-startup-id /usr/local/bin/alpine-usb-polkit-agent
exec --no-startup-id /usr/local/bin/alpine-usb-nm-applet
exec --no-startup-id /usr/local/bin/alpine-usb-blueman-applet
bindsym $mod+Return exec xterm
bindsym $mod+d exec dmenu_run
bindsym $mod+Shift+q kill
bindsym $mod+Shift+r restart
bindsym $mod+Shift+e exec "i3-nagbar -t warning -m 'Exit i3?' -B 'Yes' 'i3-msg exit'"
bar { status_command i3status }
EOF
fi

if has_word sway "$TILING_WMS"; then
  mkdir -p /etc/skel/.config/sway
  cat > /etc/skel/.config/sway/config <<EOF
set \$mod Mod4
input * {
    xkb_layout "$XKB_LAYOUT"
    xkb_variant "$XKB_VARIANT"
}
exec /usr/local/bin/alpine-usb-polkit-agent
exec /usr/local/bin/alpine-usb-nm-applet
exec /usr/local/bin/alpine-usb-blueman-applet
include /etc/sway/config
EOF
fi

if has_word bspwm "$TILING_WMS"; then
  mkdir -p /etc/skel/.config/bspwm /etc/skel/.config/sxhkd
  cat > /etc/skel/.config/bspwm/bspwmrc <<'EOF'
#!/bin/sh
/usr/local/bin/alpine-usb-polkit-agent &
/usr/local/bin/alpine-usb-nm-applet &
/usr/local/bin/alpine-usb-blueman-applet &
pgrep -x sxhkd >/dev/null 2>&1 || sxhkd &
bspc config border_width 2
bspc config window_gap 8
EOF
  chmod +x /etc/skel/.config/bspwm/bspwmrc
  cat > /etc/skel/.config/sxhkd/sxhkdrc <<'EOF'
super + Return
    xterm
super + d
    dmenu_run
super + shift + q
    bspc node -c
super + alt + r
    bspc wm -r
EOF
fi

if [ -d /etc/skel/.config ]; then
  mkdir -p "/home/$USER_NAME/.config"
  cp -a /etc/skel/.config/. "/home/$USER_NAME/.config/" 2>/dev/null || true
  chown -R "$USER_NAME:$USER_NAME" "/home/$USER_NAME/.config"
fi

cat > /etc/motd <<EOF
Alpine USB ready.
User: $USER_NAME
Initial password: configured at build time
Desktop: $DESKTOP
Window managers: ${TILING_WMS:-none}
Display manager: $DISPLAY_MANAGER
Bootloader: $BOOTLOADER
Kernel: linux-$KERNEL_FLAVOR
Keyboard layout: $XKB_LAYOUT / console $CONSOLE_KEYMAP
Change your password with: passwd
EOF

# ---- systemd-boot removable UEFI setup -----------------------------------
if [ "$BOOTLOADER" = "systemd-boot" ]; then
  mkdir -p /boot/EFI/BOOT /boot/loader/entries
  efi_src=""
  for candidate in /usr/lib/systemd/boot/efi/systemd-boot*.efi; do
    [ -f "$candidate" ] && efi_src="$candidate" && break
  done
  [ -n "$efi_src" ] || die "systemd-boot EFI binary not found"
  case "$(apk --print-arch 2>/dev/null || echo x86_64)" in
    x86_64) efi_dst="BOOTX64.EFI" ;;
    x86) efi_dst="BOOTIA32.EFI" ;;
    aarch64) efi_dst="BOOTAA64.EFI" ;;
    armv7|armhf) efi_dst="BOOTARM.EFI" ;;
    *) efi_dst="BOOTX64.EFI" ;;
  esac
  cp "$efi_src" "/boot/EFI/BOOT/$efi_dst"
  root_uuid="$(awk '$2 == "/" { sub(/^UUID=/, "", $1); print $1; exit }' /etc/fstab)"
  [ -n "$root_uuid" ] || die "Could not determine root UUID for systemd-boot"
  modules="$(printf '%s' "$INITFS_FEATURES" | tr ' ' ',')"
  cat > /boot/loader/loader.conf <<EOF
default alpine.conf
timeout $BOOT_TIMEOUT
editor no
console-mode $SYSTEMD_BOOT_CONSOLE_MODE
EOF
  cat > /boot/loader/entries/alpine.conf <<EOF
title Alpine Linux USB
linux /vmlinuz-$KERNEL_FLAVOR
initrd /initramfs-$KERNEL_FLAVOR
options root=UUID=$root_uuid ro rootfstype=$ROOTFS rootwait rootdelay=5 modules=$modules console=tty0
EOF
  cat > /boot/loader/entries/alpine-safe.conf <<EOF
title Alpine Linux USB (safe graphics)
linux /vmlinuz-$KERNEL_FLAVOR
initrd /initramfs-$KERNEL_FLAVOR
options root=UUID=$root_uuid ro rootfstype=$ROOTFS rootwait rootdelay=5 modules=$modules console=tty0 nomodeset
EOF
fi

# Valid machine-id needed for dbus/display managers at first boot.
rm -f /etc/machine-id
if command -v dbus-uuidgen >/dev/null 2>&1; then
  dbus-uuidgen --ensure=/etc/machine-id
fi

echo "$HOSTNAME" > /etc/hostname

echo "Alpine USB configuration complete: desktop=$DESKTOP dm=$DISPLAY_MANAGER bootloader=$BOOTLOADER kernel=linux-$KERNEL_FLAVOR"
