# Alpine USB Installer

Tool for building and flashing a bootable, preinstalled Alpine Linux x86_64 USB image.

It started as an XFCE-only builder, but now the GUI and build scripts expose a full configurable Alpine profile: desktop environment, tiling/window managers, Wi‑Fi, Bluetooth, display manager, bootloader, kernel flavor, keyboard/language, users, firmware, audio and extra APK packages.

## What it can configure

Defaults are safe and match the original experience: `linux-lts`, GRUB removable UEFI, XFCE, LightDM, NetworkManager + Wi‑Fi, Bluetooth, PipeWire, Firefox ESR, user `pablo` / password `pablo`, English locale and Latin American Spanish keyboard.

Configurable sections in the Qt app are collapsed by default:

- System, user and localization:
  - image size, Alpine branch, hostname, user/passwords
  - timezone, locale, console keymap, XKB keyboard layout/model/variant
- Desktop/session:
  - XFCE, GNOME, KDE Plasma, MATE, LXQt or no full desktop
  - optional i3, Sway, Hyprland, AwesomeWM, bspwm, Openbox, labwc
  - default session, browser, PipeWire/ALSA/no audio
- Network:
  - NetworkManager or no desktop network stack
  - Wi‑Fi support toggle
  - Bluetooth support toggle
- Boot:
  - GRUB removable UEFI or systemd-boot removable UEFI
  - `linux-lts` or `linux-stable`
  - full firmware or `linux-firmware-none`
- Extra packages:
  - arbitrary additional `apk add` package names

The generated image is meant to be written directly to a USB drive and booted as an installed Alpine system.

## Compatibility fixes

- Polkit: desktop packages are installed after `polkit-elogind` is explicitly installed, so APK does not accidentally choose the non-elogind `polkit` provider when packages such as `xfce-polkit`, GNOME, Plasma, MATE or LXQt pull a polkit agent.
- Lightweight WMs: the generated system installs a duplicate-safe polkit agent launcher for sessions such as i3, Sway, bspwm, Openbox and labwc.
- Bluetooth: the installer uses `obexd-enhanced` instead of `bluez-obexd`, avoiding the GNOME Bluetooth conflict while still providing the OBEX service.
- Keyboard: Alpine's current OpenRC console keymap service is `loadkeys`; the generated system writes `/etc/conf.d/loadkeys` and keeps `/etc/conf.d/keymaps` for compatibility.

## Requirements

Building is recommended on Linux or Docker Desktop with NBD support.

On macOS, Docker Desktop is used automatically because the build requires Linux/NBD.

On native Linux you also need `mtools`, `grub-efi`/`grub-mkstandalone`, `qemu-nbd`, `parted`, `rsync`, `dosfstools` and related image build tools.

Python GUI dependencies are listed in `requirements.txt`. The helper script creates its own `.qtvenv` automatically if needed.

## Qt GUI

```sh
./run_qt_gui.sh
```

From the GUI you can:

- choose the output image path
- open collapsed configuration sections and customize the profile
- build the image
- select a target USB drive
- flash the image

If the selector does not detect your USB drive, you can type the device manually, for example `/dev/disk7` on macOS or `/dev/sdb` on Linux.

Supported flashing helpers:

- macOS: `diskutil`, `dd`, administrator password prompt
- Linux: `lsblk`, `dd`, `sudo`/`pkexec`
- Windows: raw flashing is not implemented; use Rufus/balenaEtcher with the generated image

## CLI build examples

Default profile:

```sh
IMAGE_SIZE=16G ./build-alpine-usb.sh
```

KDE Plasma + SDDM + systemd-boot + stable kernel:

```sh
ALPINE_USB_DESKTOP=plasma \
ALPINE_USB_DISPLAY_MANAGER=sddm \
ALPINE_USB_BOOTLOADER=systemd-boot \
ALPINE_USB_KERNEL_FLAVOR=stable \
IMAGE_SIZE=32G \
./build-alpine-usb.sh
```

WM-only image with Sway and i3 through greetd:

```sh
ALPINE_USB_DESKTOP=none \
ALPINE_USB_TILING_WMS="sway i3" \
ALPINE_USB_DISPLAY_MANAGER=greetd \
./build-alpine-usb.sh
```

Spanish locale/keymap example:

```sh
ALPINE_USB_LOCALE=es_ES.UTF-8 \
ALPINE_USB_TIMEZONE=Europe/Madrid \
ALPINE_USB_CONSOLE_KEYMAP=es \
ALPINE_USB_XKB_LAYOUT=es \
./build-alpine-usb.sh
```

Result by default:

```txt
alpine-usb.img
```

## Write to USB

⚠️ This completely erases the target device.

On macOS:

```sh
diskutil unmountDisk /dev/diskX
sudo dd if=alpine-usb.img of=/dev/rdiskX bs=4M status=progress
sync
diskutil eject /dev/diskX
```

On Linux:

```sh
lsblk
sudo dd if=alpine-usb.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Use the whole disk (`/dev/sdX`, `/dev/diskX`), not a partition (`/dev/sdX1`).

## Initial login

Default credentials unless changed in the GUI/CLI:

```txt
user: pablo
password: pablo
root password: pablo
```

Change passwords after the first boot:

```sh
passwd
sudo passwd root
```

## Validation

Dry-run all supported option combinations without installing packages:

```sh
scripts/validate-config-matrix.sh
```

Check representative profiles with Alpine's real APK dependency solver inside Docker:

```sh
scripts/check-apk-solver.sh
```

These validate the shell configuration logic, package-list generation, display-manager/session compatibility, bootloader/kernel option handling, and real package conflicts.

A real Docker/macOS build was also tested with GNOME + Bluetooth + GRUB UEFI to verify the previous `bluez-obexd`/`obexd-enhanced` conflict is fixed.

## License

MIT
