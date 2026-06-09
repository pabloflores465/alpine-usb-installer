#!/bin/sh
# Runs inside target Alpine image/chroot via alpine-make-vm-image.
set -eux

# ---- Base system ----
apk update
apk upgrade --available

apk add \
  alpine-base \
  linux-lts linux-firmware \
  eudev seatd acpid kbd upower \
  chrony \
  dbus dbus-x11 elogind polkit-elogind xfce-polkit \
  networkmanager networkmanager-cli networkmanager-tui networkmanager-wifi network-manager-applet wireless-regdb wpa_supplicant gnome-keyring \
  xfce4 xfce4-terminal xfce4-screensaver xfce4-power-manager xfce4-notifyd \
  lightdm lightdm-gtk-greeter accountsservice \
  xorg-server xinit setxkbmap xkeyboard-config libinput xf86-input-libinput xf86-video-amdgpu xf86-video-ati xf86-video-intel xf86-video-nouveau xf86-video-vesa xf86-video-fbdev \
  mesa-dri-gallium mesa-egl mesa-gl \
  gvfs udisks2 thunar-volman \
  pipewire wireplumber pipewire-pulse alsa-utils pavucontrol \
  firefox-esr \
  font-noto font-noto-emoji terminus-font \
  doas sudo \
  bash zsh curl wget git nano vim htop less \
  e2fsprogs dosfstools lsblk blkid util-linux \
  grub grub-efi efibootmgr

# ---- English OS + Latin American Spanish keyboard ----
# Alpine uses musl; full glibc locale generation is not needed here.
mkdir -p /etc/profile.d /etc/X11/xorg.conf.d
cat > /etc/profile.d/00-lang.sh <<'EOF'
export LANG=en_US.UTF-8
export LANGUAGE=en_US:en
export LC_MESSAGES=en_US.UTF-8
EOF
chmod +x /etc/profile.d/00-lang.sh
cat > /etc/environment <<'EOF'
LANG=en_US.UTF-8
LANGUAGE=en_US:en
LC_MESSAGES=en_US.UTF-8
EOF
cat > /etc/locale.conf <<'EOF'
LANG=en_US.UTF-8
EOF

cat > /etc/conf.d/keymaps <<'EOF'
# Console keymap. Xorg/LightDM use the XKB "latam" layout below.
KEYMAP="la-latin1"
WINDOWKEYS="YES"
EXTENDED_KEYMAPS=""
DUMPKEYS_CHARSET=""
FIX_euro="NO"
EOF

cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<'EOF'
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "latam"
    Option "XkbModel" "pc105"
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

# LightDM keyboard + greeter. It should show LightDM first, then start XFCE.
mkdir -p /etc/lightdm/lightdm.conf.d /usr/local/bin
cat > /usr/local/bin/alpine-usb-setxkbmap-latam <<'EOF'
#!/bin/sh
/usr/bin/setxkbmap latam 2>/dev/null || true
EOF
chmod +x /usr/local/bin/alpine-usb-setxkbmap-latam
cat > /etc/lightdm/lightdm.conf.d/50-alpine-usb.conf <<'EOF'
[Seat:*]
greeter-session=lightdm-gtk-greeter
user-session=xfce
allow-guest=false
display-setup-script=/usr/local/bin/alpine-usb-setxkbmap-latam
greeter-setup-script=/usr/local/bin/alpine-usb-setxkbmap-latam
EOF
cat > /etc/lightdm/lightdm-gtk-greeter.conf <<'EOF'
[greeter]
indicators=~host;~spacer;~clock;~spacer;~session;~language;~a11y;~power
clock-format=%a, %b %d  %H:%M
EOF

# ---- User ----
# Create a normal primary group for pablo, then add desktop/admin groups.
if ! getent group pablo >/dev/null 2>&1; then
  addgroup pablo
fi
if ! id pablo >/dev/null 2>&1; then
  adduser -D -s /bin/bash -G pablo pablo
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

# Default LightDM/XFCE session for the initial user, plus a TTY fallback.
cat > /home/pablo/.dmrc <<'EOF'
[Desktop]
Session=xfce
Language=en_US.UTF-8
EOF
cat > /home/pablo/.xinitrc <<'EOF'
#!/bin/sh
setxkbmap latam 2>/dev/null || true
exec startxfce4
EOF
chmod +x /home/pablo/.xinitrc
chown pablo:pablo /home/pablo/.dmrc /home/pablo/.xinitrc

# Make sure the tray applet and polkit agent exist in XFCE even if package
# autostart entries change upstream.
mkdir -p /usr/local/bin /etc/xdg/autostart
cat > /usr/local/bin/alpine-usb-nm-applet <<'EOF'
#!/bin/sh
command -v nm-applet >/dev/null 2>&1 || exit 0
exec nm-applet
EOF
chmod +x /usr/local/bin/alpine-usb-nm-applet
cat > /etc/xdg/autostart/alpine-usb-nm-applet.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Network Manager Applet
Exec=/usr/local/bin/alpine-usb-nm-applet
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
EOF
cat > /usr/local/bin/alpine-usb-polkit-agent <<'EOF'
#!/bin/sh
for agent in \
  /usr/lib/xfce4/xfce-polkit \
  /usr/libexec/xfce-polkit \
  /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
 do
  [ -x "$agent" ] && exec "$agent"
done
exit 0
EOF
chmod +x /usr/local/bin/alpine-usb-polkit-agent
cat > /etc/xdg/autostart/alpine-usb-polkit-agent.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=PolicyKit Authentication Agent
Exec=/usr/local/bin/alpine-usb-polkit-agent
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
EOF

# Allow local active wheel users to power off/reboot/suspend from XFCE/LightDM
# instead of being bounced back to the display manager.
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
    if (powerActions.indexOf(action.id) >= 0 && subject.local && subject.active && (subject.isInGroup("wheel") || subject.user == "lightdm")) {
        return polkit.Result.YES;
    }
    if (action.id.indexOf("org.freedesktop.NetworkManager.") === 0 && subject.local && subject.active && subject.isInGroup("plugdev")) {
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

# ---- Services: boot to display manager ----
rc-update add devfs sysinit || true
rc-update add dmesg sysinit || true
rc-update del mdev sysinit || true
rc-update add udev sysinit || true
rc-update add udev-trigger sysinit || true
rc-update add udev-settle sysinit || true
rc-update add hwdrivers sysinit || true
rc-update add modules boot || true
rc-update add keymaps boot || true
rc-update add sysctl boot || true
rc-update add hostname boot || true
rc-update add bootmisc boot || true
rc-update add syslog boot || true
rc-update add networking boot || true
rc-update add chronyd default || true
rc-update add dbus default
rc-update add elogind default
rc-update add polkit default || true
rc-update add seatd default || true
rc-update add acpid default || true
rc-update add wpa_supplicant default || true
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
sed -i 's/[[:space:]]relatime[[:space:]]/ noatime /' /etc/fstab 2>/dev/null || true
grep -q '^tmpfs /tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab
grep -q '^tmpfs /var/tmp ' /etc/fstab 2>/dev/null || echo 'tmpfs /var/tmp tmpfs defaults,noatime,mode=1777 0 0' >> /etc/fstab

# ---- NetworkManager: allow users to manage network ----
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

# ---- XFCE defaults ----
mkdir -p /etc/skel/Desktop
cat > /etc/skel/.xinitrc <<'EOF'
#!/bin/sh
setxkbmap latam 2>/dev/null || true
exec startxfce4
EOF
chmod +x /etc/skel/.xinitrc
mkdir -p /etc/xdg/xfce4/xfconf/xfce-perchannel-xml
cat > /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/keyboard-layout.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="keyboard-layout" version="1.0">
  <property name="Default" type="empty">
    <property name="XkbDisable" type="bool" value="false"/>
    <property name="XkbLayout" type="string" value="latam"/>
    <property name="XkbVariant" type="string" value=""/>
  </property>
</channel>
EOF
cat > /etc/motd <<'EOF'
Alpine USB ready.
User: pablo
Initial password: pablo
Change your password with: passwd
Keyboard layout: Latin American Spanish
EOF

# Valid machine-id needed for dbus/lightdm at first boot.
rm -f /etc/machine-id
if command -v dbus-uuidgen >/dev/null 2>&1; then
  dbus-uuidgen --ensure=/etc/machine-id
fi

# Stable hostname.
echo 'alpine-usb' > /etc/hostname

# Done.
