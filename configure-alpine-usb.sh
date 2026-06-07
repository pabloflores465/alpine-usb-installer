#!/bin/sh
# Runs inside target Alpine image/chroot via alpine-make-vm-image.
set -eux

# ---- Base system ----
apk update
apk upgrade --available

apk add \
  alpine-base \
  linux-lts \
  eudev seatd \
  chrony \
  dbus elogind \
  networkmanager network-manager-applet \
  xfce4 xfce4-terminal xfce4-screensaver \
  lightdm lightdm-gtk-greeter \
  xorg-server xf86-input-libinput xf86-video-amdgpu xf86-video-ati xf86-video-vesa \
  mesa-dri-gallium mesa-egl \
  gvfs udisks2 thunar-volman \
  pipewire wireplumber pipewire-pulse alsa-utils pavucontrol \
  firefox-esr \
  font-noto font-noto-emoji terminus-font \
  doas sudo \
  bash zsh curl wget git nano vim htop less \
  e2fsprogs dosfstools lsblk blkid util-linux \
  grub grub-efi efibootmgr

# ---- Spanish keyboard/locale-ish config ----
# Alpine uses musl; full glibc locales are not standard. Set useful env + console keymap.
mkdir -p /etc/profile.d /etc/X11/xorg.conf.d
cat > /etc/profile.d/00-lang.sh <<'EOF'
export LANG=es_ES.UTF-8
export LC_ALL=es_ES.UTF-8
EOF
chmod +x /etc/profile.d/00-lang.sh

cat > /etc/conf.d/keymaps <<'EOF'
KEYMAP="es"
WINDOWKEYS="YES"
EXTENDED_KEYMAPS=""
DUMPKEYS_CHARSET=""
FIX_euro="NO"
EOF

cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<'EOF'
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "es"
    Option "XkbModel" "pc105"
EndSection
EOF

# LightDM keyboard + greeter.
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-alpine-usb.conf <<'EOF'
[Seat:*]
greeter-session=lightdm-gtk-greeter
user-session=xfce
EOF

# ---- User ----
if ! id pablo >/dev/null 2>&1; then
  adduser -D -s /bin/bash -G wheel pablo
fi
echo 'pablo:pablo' | chpasswd
echo 'root:pablo' | chpasswd
addgroup pablo wheel || true
addgroup pablo audio || true
addgroup pablo video || true
addgroup pablo input || true
addgroup pablo plugdev || true
addgroup pablo netdev || true
addgroup pablo seat || true
addgroup pablo tty || true

mkdir -p /etc/doas.d
cat > /etc/doas.d/doas.conf <<'EOF'
permit persist :wheel
EOF
chmod 600 /etc/doas.d/doas.conf

# sudo fallback for tools/users expecting sudo.
echo '%wheel ALL=(ALL:ALL) ALL' > /etc/sudoers.d/wheel
chmod 440 /etc/sudoers.d/wheel

# Allow local users to start Xorg from tty if LightDM fails.
mkdir -p /etc/X11
cat > /etc/X11/Xwrapper.config <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# ---- Services: boot to display manager ----
rc-update add devfs sysinit || true
rc-update add dmesg sysinit || true
rc-update del mdev sysinit || true
rc-update add udev sysinit || true
rc-update add udev-trigger sysinit || true
rc-update add udev-settle sysinit || true
rc-update add hwdrivers sysinit || true
rc-update add modules boot || true
rc-update add sysctl boot || true
rc-update add hostname boot || true
rc-update add bootmisc boot || true
rc-update add syslog boot || true
rc-update add networking boot || true
rc-update add chronyd default || true
rc-update add dbus default
rc-update add elogind default
rc-update add seatd default || true
rc-update add networkmanager default
rc-update add udisks2 default
rc-update add lightdm default

# Prefer NetworkManager over classic network scripts for desktop.
rc-update del networking default || true

# ---- USB-friendly optimizations ----
# noatime reduces writes. tmpfs for temp/cache/log volatility.
# build script also patches root fstab after partition UUID known.
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

# Keep apk cache disabled by default to avoid USB writes.
rm -rf /var/cache/apk/* || true

# fstab extras safe even before root line exists.
grep -q '^tmpfs /tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab
grep -q '^tmpfs /var/tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /var/tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab

# ---- NetworkManager: allow users to manage network ----
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/10-globally-managed-devices.conf <<'EOF'
[keyfile]
unmanaged-devices=none
EOF

# ---- XFCE defaults ----
mkdir -p /etc/skel/Desktop
cat > /etc/motd <<'EOF'
Alpine USB listo.
Usuario: pablo
Password inicial: pablo
Cambia password con: passwd
EOF

# Valid machine-id needed for dbus/lightdm at first boot.
rm -f /etc/machine-id
if command -v dbus-uuidgen >/dev/null 2>&1; then
  dbus-uuidgen --ensure=/etc/machine-id
fi

# Stable hostname.
echo 'alpine-usb' > /etc/hostname

# Done.
