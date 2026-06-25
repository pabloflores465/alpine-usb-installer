#!/bin/sh
# Validate and materialize a RHEL-family USB root configuration.
set -eu

die() { echo "ERROR: $*" >&2; exit 1; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
is_enabled() { case "$(lower "${1:-0}")" in 1|yes|true|on|enabled) return 0 ;; *) return 1 ;; esac; }

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

safe_token() {
  name="$1"; value="$2"
  case "$value" in *[!A-Za-z0-9_.,@%+=:/-]*|"") die "$name contains unsupported characters: $value" ;; esac
}
safe_optional_token() { [ -z "$2" ] || safe_token "$1" "$2"; }
safe_package_name() { case "$1" in ""|-*|*[!A-Za-z0-9+_.:@-]*) die "Invalid package name: $1" ;; esac; }
has_word() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

DISTRO="$(lower "${RHEL_USB_DISTRO:-rocky}")"
RELEASE="${RHEL_USB_RELEASE:-9}"
PROFILE="${RHEL_USB_PROFILE:-compatibility}"
USER_NAME="${RHEL_USB_USER:-linux}"
USER_PASSWORD="$(read_secret_value RHEL_USB_PASSWORD_FILE RHEL_USB_PASSWORD linux)"
ROOT_PASSWORD="$(read_secret_value RHEL_USB_ROOT_PASSWORD_FILE RHEL_USB_ROOT_PASSWORD "$USER_PASSWORD")"
HOSTNAME="${RHEL_USB_HOSTNAME:-ledit-rhel}"
TIMEZONE="${RHEL_USB_TIMEZONE:-UTC}"
LOCALE="${RHEL_USB_LOCALE:-en_US.UTF-8}"
CONSOLE_KEYMAP="${RHEL_USB_CONSOLE_KEYMAP:-us}"
XKB_LAYOUT="${RHEL_USB_XKB_LAYOUT:-us}"
XKB_VARIANT="${RHEL_USB_XKB_VARIANT:-}"
XKB_MODEL="${RHEL_USB_XKB_MODEL:-pc105}"
DESKTOP="$(lower "${RHEL_USB_DESKTOP:-xfce}")"
DISPLAY_MANAGER="$(lower "${RHEL_USB_DISPLAY_MANAGER:-auto}")"
DEFAULT_SESSION="$(lower "${RHEL_USB_DEFAULT_SESSION:-auto}")"
NETWORK_BACKEND="$(lower "${RHEL_USB_NETWORK:-networkmanager}")"
WIFI="${RHEL_USB_WIFI:-1}"
BLUETOOTH="${RHEL_USB_BLUETOOTH:-1}"
AUDIO="$(lower "${RHEL_USB_AUDIO:-pipewire}")"
BROWSER="$(lower "${RHEL_USB_BROWSER:-firefox}")"
FIRMWARE="$(lower "${RHEL_USB_FIRMWARE:-full}")"
BOOTLOADER="$(lower "${RHEL_USB_BOOTLOADER:-grub}")"
KERNEL_FLAVOR="$(lower "${RHEL_USB_KERNEL_FLAVOR:-stable}")"
BOOT_TIMEOUT="${RHEL_USB_BOOT_TIMEOUT:-3}"
AUTO_RESIZE="${RHEL_USB_AUTO_RESIZE:-1}"
TILING_WMS="$(printf '%s' "${RHEL_USB_TILING_WMS:-}" | tr ',;:' '   ')"
EXTRA_PACKAGES="${RHEL_USB_EXTRA_PACKAGES:-}"
PACKAGE_LIST="${RHEL_USB_PACKAGE_LIST:-}"
DRY_RUN="${RHEL_USB_DRY_RUN:-0}"

case "$DISTRO" in rhel|rocky|alma|centos-stream) ;; *) die "Unsupported RHEL-family distro: $DISTRO" ;; esac
[ "$DISTRO" = rhel ] && DISTRO=rocky
case "$RELEASE" in 9|10|[0-9]) ;; *) die "Unsupported RHEL-family release: $RELEASE" ;; esac
case "$PROFILE" in compatibility|minimal|"") ;; *) die "Unsupported profile: $PROFILE" ;; esac
case "$USER_NAME" in [a-z_]*) ;; *) die "Username must start with a lowercase letter or underscore" ;; esac
case "$USER_NAME" in *[!a-z0-9_-]*) die "Username may contain only lowercase letters, numbers, underscore and dash" ;; esac
case "$USER_PASSWORD$ROOT_PASSWORD" in *:*|*"\n"*) die "Passwords may not contain ':' or newlines" ;; esac
case "$HOSTNAME" in ""|-*|*-) die "Hostname must not be empty or start/end with '-'" ;; esac
case "$HOSTNAME" in *[!A-Za-z0-9-]*) die "Hostname may contain only letters, numbers and dash" ;; esac
safe_token Timezone "$TIMEZONE"
safe_token Locale "$LOCALE"
safe_token "Console keymap" "$CONSOLE_KEYMAP"
safe_token "XKB layout" "$XKB_LAYOUT"
safe_optional_token "XKB variant" "$XKB_VARIANT"
safe_token "XKB model" "$XKB_MODEL"
case "$BOOT_TIMEOUT" in *[!0-9]*|"") die "Boot timeout must be a number" ;; esac
case "$(lower "$AUTO_RESIZE")" in 1|yes|true|on|enabled|0|no|false|off|disabled) ;; *) die "Unsupported auto-resize value: $AUTO_RESIZE" ;; esac
case "$DESKTOP" in xfce|gnome|plasma|mate|lxqt|none) ;; *) die "Unsupported desktop: $DESKTOP" ;; esac
case "$DISPLAY_MANAGER" in auto|lightdm|sddm|gdm|none) ;; lxdm|greetd) die "Display manager $DISPLAY_MANAGER is not mapped for RHEL-family" ;; *) die "Unsupported display manager: $DISPLAY_MANAGER" ;; esac
case "$NETWORK_BACKEND" in networkmanager|none) ;; *) die "Unsupported network backend: $NETWORK_BACKEND" ;; esac
case "$AUDIO" in pipewire|alsa|none) ;; *) die "Unsupported audio option: $AUDIO" ;; esac
case "$BROWSER" in firefox-esr|firefox|chromium|none) ;; *) die "Unsupported browser: $BROWSER" ;; esac
case "$FIRMWARE" in full|none) ;; *) die "Unsupported firmware option: $FIRMWARE" ;; esac
case "$BOOTLOADER" in grub) ;; systemd-boot|systemdboot) die "systemd-boot installroot flow is not implemented for RHEL-family; use grub" ;; *) die "Unsupported bootloader: $BOOTLOADER" ;; esac
case "$KERNEL_FLAVOR" in stable|lts) ;; *) die "Unsupported kernel flavor: $KERNEL_FLAVOR" ;; esac
VALID_WMS="i3 sway openbox"
for wm in $TILING_WMS; do has_word "$wm" "$VALID_WMS" || die "Unsupported RHEL-family window manager: $wm"; done
for pkg in $EXTRA_PACKAGES $PACKAGE_LIST; do safe_package_name "$pkg"; done

if [ "$DEFAULT_SESSION" = auto ]; then
  if [ "$DESKTOP" != none ]; then DEFAULT_SESSION="$DESKTOP"; else set -- $TILING_WMS; DEFAULT_SESSION="${1:-shell}"; fi
fi
case "$DEFAULT_SESSION" in xfce|gnome|plasma|mate|lxqt|i3|sway|openbox|shell) ;; *) die "Unsupported default session: $DEFAULT_SESSION" ;; esac

if is_enabled "$DRY_RUN"; then
  echo "RHEL-family dry-run OK"
  echo "distro=$DISTRO release=$RELEASE desktop=$DESKTOP display_manager=$DISPLAY_MANAGER"
  echo "packages=$PACKAGE_LIST"
  exit 0
fi

ROOTFS="${1:-/}"
mkdir -p "$ROOTFS/etc" "$ROOTFS/etc/sysconfig" "$ROOTFS/etc/sudoers.d" "$ROOTFS/usr/local/sbin"
printf '%s\n' "$HOSTNAME" > "$ROOTFS/etc/hostname"
printf 'LANG=%s\n' "$LOCALE" > "$ROOTFS/etc/locale.conf"
printf 'KEYMAP=%s\n' "$CONSOLE_KEYMAP" > "$ROOTFS/etc/vconsole.conf"
printf 'ZONE=%s\n' "$TIMEZONE" > "$ROOTFS/etc/sysconfig/clock"
printf '%s ALL=(ALL) NOPASSWD: ALL\n' "$USER_NAME" > "$ROOTFS/etc/sudoers.d/90-linux-usb-user"
chmod 0440 "$ROOTFS/etc/sudoers.d/90-linux-usb-user"
cat > "$ROOTFS/usr/local/sbin/linux-usb-firstboot" <<'SCRIPT'
#!/bin/sh
set -eu
if command -v growpart >/dev/null 2>&1; then
  rootdev=$(findmnt -n -o SOURCE / || true)
  case "$rootdev" in *[0-9]) disk=${rootdev%[0-9]*}; part=${rootdev##*[!0-9]} ;; *) disk=""; part="" ;; esac
  [ -n "$disk" ] && growpart "$disk" "$part" || true
fi
if command -v xfs_growfs >/dev/null 2>&1; then xfs_growfs / || true; fi
if command -v resize2fs >/dev/null 2>&1; then resize2fs "$(findmnt -n -o SOURCE /)" || true; fi
systemctl disable linux-usb-firstboot.service || true
SCRIPT
chmod 0755 "$ROOTFS/usr/local/sbin/linux-usb-firstboot"
mkdir -p "$ROOTFS/etc/systemd/system"
cat > "$ROOTFS/etc/systemd/system/linux-usb-firstboot.service" <<'UNIT'
[Unit]
Description=Expand Linux USB root filesystem on first boot
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/linux-usb-firstboot
[Install]
WantedBy=multi-user.target
UNIT
