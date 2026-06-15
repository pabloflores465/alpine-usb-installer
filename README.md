# Alpine USB Installer

Build and flash configurable, preinstalled **Alpine Linux x86_64 USB images** from a Qt GUI or one unified terminal binary (TUI + CLI commands).

> License: GPL-2.0-only. See [`LICENSE`](LICENSE).

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Interfaces](#interfaces)
  - [GUI](#gui)
  - [TUI](#tui)
  - [CLI](#cli)
- [Default profile](#default-profile)
- [Configuration guide](#configuration-guide)
- [Write to USB](#write-to-usb)
- [Booting the USB](#booting-the-usb)
  - [Intel Macs](#intel-macs)
  - [HP ProBook 4440s / older HP laptops](#hp-probook-4440s--older-hp-laptops)
- [Initial login](#initial-login)
- [macOS DMG packaging](#macos-dmg-packaging)
- [Validation and tests](#validation-and-tests)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- Build a bootable, installed Alpine Linux USB image.
- Configure desktop/session options:
  - XFCE, GNOME, KDE Plasma, MATE, LXQt, or no full desktop.
  - Optional i3, Sway, Hyprland, AwesomeWM, bspwm, Openbox, labwc.
- Configure boot, kernel, firmware, keyboard, locale, users, Wi‑Fi, Bluetooth, audio, browser, and extra APK packages.
- Search Alpine `main` + `community` packages from the GUI/TUI/CLI.
- Flash the generated image to USB from macOS/Linux.
- Auto-expand the root filesystem on first boot to use the full USB drive.

## Requirements

### Build host

- Python 3.
- Docker Desktop on macOS. The build needs Linux/NBD support.
- On native Linux: `mtools`, GRUB EFI tooling, `qemu-nbd`, `parted`, `rsync`, `dosfstools`, and normal image build tools.

### Runtime tools

- macOS flashing: `diskutil`, `dd`, administrator password.
- Linux flashing: `lsblk`, `dd`, `sudo` or `pkexec`.
- Windows raw flashing is not implemented here. Use Rufus or balenaEtcher with the generated image.

## Quick start

```sh
# GUI
./gui.py

# Unified terminal binary: TUI by default
./alpine-usb
# or explicit TUI
./alpine-usb tui

# CLI help/subcommands
./alpine-usb --help
```

Default output path:

```txt
/tmp/alpine-usb-installer/alpine-usb.img
```

## Interfaces

### GUI

```sh
./gui.py
```

`./gui.py` creates and uses its own `.qtvenv` automatically if PySide6 is missing.

GUI flow:

1. Set image output path.
2. Open only the configuration sections you want to change.
3. Review the live configuration summary.
4. Build the image.
5. Select USB target.
6. Flash USB.

If USB auto-detection fails, type the device manually, for example `/dev/disk7` on macOS or `/dev/sdb` on Linux.

### TUI

```sh
./alpine-usb
# or explicit:
./alpine-usb tui
```

The TUI provides full-screen menus for configuration, package search, dry-run/build, USB device selection, flashing, and host diagnostics. There is one terminal entrypoint, `alpine-usb`; `cli.py` and `tui.py` are import-only support modules.

### CLI

```sh
./alpine-usb --help
./alpine-usb build --help
```

Common commands:

```sh
# Search packages
./alpine-usb search firefox

# Validate a profile without building
./alpine-usb build --dry-run --desktop xfce --bootloader systemd-boot

# Build default profile without prompts
./alpine-usb build -y

# Build Plasma profile
./alpine-usb build --desktop plasma --display-manager sddm --bootloader systemd-boot -y

# List removable devices
./alpine-usb devices

# Flash image to USB
./alpine-usb flash /tmp/alpine-usb-installer/alpine-usb.img /dev/sdX
```

Extra packages can be repeated or space-separated:

```sh
./alpine-usb build \
  --extra-package neovim \
  --extra-package "tmux htop" \
  --extra-package docker
```

## Default profile

Defaults are generic and distro-like:

| Option | Default |
| --- | --- |
| Image size | `16G` |
| Output | `/tmp/alpine-usb-installer/alpine-usb.img` |
| Alpine branch | `latest-stable` |
| Architecture | `x86_64` |
| User/password | `alpine` / `alpine` |
| Root password | `alpine` |
| Locale/timezone | `en_US.UTF-8` / `UTC` |
| Keyboard | US console + XKB |
| Desktop | XFCE |
| Display manager | auto recommended, usually LightDM for XFCE/MATE |
| Bootloader | GRUB removable UEFI |
| Kernel | `linux-lts` |
| Firmware | full firmware |
| Network | NetworkManager + Wi‑Fi |
| Bluetooth | enabled |
| Audio | PipeWire + WirePlumber + pipewire-pulse |
| Browser | Firefox |
| USB auto-resize | enabled |

## Configuration guide

### System, user, localization

Configure image size, Alpine branch, hostname, username/passwords, timezone, locale, console keymap, and XKB layout.

### Desktop/session

Choose a desktop, display manager, default session, browser, audio backend, and optional window managers.

Recommended compatibility:

- Older hardware: XFCE + LightDM + GRUB + `linux-lts`.
- Modern KDE setup: Plasma + SDDM.
- GNOME setup: GNOME + GDM.
- WM-only setup: no desktop + greetd or no display manager.
- Wayland sessions such as Sway/Hyprland/labwc: use Auto, greetd, SDDM, GDM, or no display manager. LightDM/LXDM are treated as X11-only here.

### Network, Wi‑Fi, Bluetooth

NetworkManager is recommended for desktop usage. Bluetooth uses `obexd-enhanced` to avoid conflicts with GNOME Bluetooth while still providing OBEX support.

### Audio

PipeWire is the recommended default. On Alpine/OpenRC there is no `systemd --user` manager, so the generated desktop image starts `pipewire`, `wireplumber`, and `pipewire-pulse` from XDG autostart.

### Bootloader, kernel, firmware

- GRUB removable UEFI is the safest default across many PCs and Intel Macs.
- systemd-boot removable UEFI is available for UEFI-focused systems.
- `linux-lts` is recommended for stability.
- Full firmware is recommended for laptops and Wi‑Fi/Bluetooth hardware.

### Extra APK packages

Use official Alpine package names. Package search queries Alpine `main` and `community` indexes.

## Write to USB

> Warning: flashing completely erases the selected device.

Use the whole disk (`/dev/sdX`, `/dev/diskX`), not a partition (`/dev/sdX1`, `/dev/diskXs1`). Do not copy `alpine-usb.img` as a file onto a FAT/exFAT USB; write it raw to the whole device.

### macOS

```sh
diskutil list
diskutil unmountDisk /dev/diskX
sudo dd if=/tmp/alpine-usb-installer/alpine-usb.img of=/dev/rdiskX bs=4m status=progress
sync
diskutil eject /dev/diskX
```

### Linux

```sh
lsblk
sudo dd if=/tmp/alpine-usb-installer/alpine-usb.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

## Booting the USB

General flow:

1. Shut down target computer.
2. Insert flashed USB drive.
3. Open one-time boot menu during power-on.
4. Choose USB drive.
5. If both `UEFI: <usb>` and non-UEFI USB entries exist:
   - Modern machines: try `UEFI: <usb>` first.
   - Older BIOS/CSM machines: try non-UEFI `USB Hard Drive` first.

Firmware settings if boot fails:

- Enable USB boot.
- Disable Secure Boot unless your firmware accepts this image.
- Disable Fast Boot if USB is skipped.
- For older systems, enable Legacy Support / CSM / Legacy Boot.
- Move USB above internal disk in boot order, or use one-time boot menu.
- Try another USB port, especially USB 2.0 on older machines.
- Reflash raw to whole disk if USB does not appear.

Common keys:

| Vendor | Boot menu | BIOS/Setup |
| --- | --- | --- |
| HP | `Esc` then `F9` | `Esc` then `F10` |
| Dell | `F12` | `F2` |
| Lenovo ThinkPad | `F12` | `F1` |
| Lenovo IdeaPad | `F12` or Novo button | `F2` or Novo button |
| Acer | `F12` | `F2` |
| ASUS | `Esc` | `F2` or `Del` |
| MSI | `F11` | `Del` |
| Gigabyte | `F12` | `Del` |
| Intel NUC | `F10` | `F2` |
| Apple Intel Mac | hold `Option` / `Alt` | Recovery / Startup Security Utility for T2 |

### Intel Macs

Intel Macs can boot the generated `x86_64` image. Apple Silicon Macs can build and flash it, but cannot boot this x86_64 Alpine image natively.

Recommended Intel Mac profile:

- `Arch`: `x86_64`
- `Bootloader`: `GRUB`
- `Kernel`: `linux-lts`
- `Firmware`: full firmware enabled
- `Desktop`: `XFCE`
- `Display manager`: `LightDM`
- `Network`: `NetworkManager`
- `Wi‑Fi`: enabled
- `Bluetooth`: enabled
- `Auto-resize USB`: enabled

Boot:

1. Shut down Mac.
2. Insert flashed USB drive.
3. Power on while holding `Option` / `Alt`.
4. Choose `EFI Boot` or orange USB icon.

If USB does not appear:

- Try another USB port.
- Try a simple USB 2.0 hub on older Macs.
- Reflash raw to whole disk.
- Use GRUB instead of systemd-boot.
- On T2 Intel Macs, allow external boot.

T2 setup:

1. Boot macOS Recovery with `Cmd` + `R`.
2. Open `Utilities` → `Startup Security Utility`.
3. Set `Secure Boot` to `No Security` if needed.
4. Set `External Boot` to `Allow booting from external media`.
5. Reboot while holding `Option` / `Alt`.

### HP ProBook 4440s / older HP laptops

The HP ProBook 4440s is an older BIOS/UEFI hybrid laptop.

Recommended profile:

- XFCE
- LightDM
- GRUB
- `linux-lts`
- Full firmware
- NetworkManager + Wi‑Fi
- Auto-resize enabled

BIOS setup:

1. Power on and press `Esc` repeatedly.
2. Press `F10` for BIOS Setup.
3. Open `System Configuration` → `Boot Options`.
4. Set:
   - `USB Boot`: enabled
   - `Secure Boot`: disabled
   - `Legacy Support`: enabled
   - `Fast Boot`: disabled, if present
5. Move `USB Hard Drive` / `USB Diskette on Key` above internal disk, or use one-time boot.
6. Save with `F10`.
7. Reboot, press `Esc`, then `F9`.
8. Pick non-UEFI `USB Hard Drive` first. If it fails, try `UEFI: USB`.

## Initial login

Defaults unless changed:

```txt
user: alpine
password: alpine
root password: alpine
```

Change passwords after first boot:

```sh
passwd
sudo passwd root
```

## macOS DMG packaging

Build a DMG on macOS with:

```sh
scripts/build-macos-dmg.sh
```

Build all release assets with:

```sh
scripts/package-release-assets.sh 0.1.7
```

The release packager creates separate GUI and terminal assets:

- `alpine-usb-installer-<version>-macos-arm64-gui.dmg` contains only `Alpine USB Installer.app`.
- `alpine-usb-installer-<version>-macos-arm64-terminal.tar.gz` contains only the standalone `alpine-usb` terminal binary.

The terminal binary is shipped as `.tar.gz` because raw GitHub asset downloads do not preserve Unix executable bits. The terminal binary carries the build resources it needs and copies them to `/tmp/alpine-usb-installer/terminal-runtime` before invoking build scripts.

## Validation and tests

Dry-run option matrix:

```sh
scripts/validate-config-matrix.sh
```

Check representative profiles with Alpine APK dependency solver inside Docker:

```sh
scripts/check-apk-solver.sh
```

Unified terminal smoke tests:

```sh
scripts/test-cli.sh
```

## Troubleshooting

### USB does not boot

- Confirm image was flashed raw to whole disk.
- Try GRUB bootloader.
- Disable Secure Boot.
- Try UEFI and legacy entries.
- Try another USB port.
- Rebuild with full firmware.

### No Wi‑Fi or Bluetooth

- Use full firmware.
- Enable Wi‑Fi/Bluetooth toggles.
- Prefer NetworkManager for desktops.
- Check device support in Alpine for that chipset.

### No desktop audio control

- Use PipeWire audio.
- Rebuild with current image: generated desktops autostart PipeWire session components under OpenRC/elogind.
- Check logs after boot:

```sh
ls /tmp/alpine-usb-*pipewire*.log /tmp/alpine-usb-wireplumber.log 2>/dev/null
```

### GUI modal appears in wrong place on macOS tiling WMs

The Qt GUI forces dialogs visible and centered. If using a tiling window manager such as AeroSpace, keep Python/PySide windows floating if your WM moves modal dialogs away from their parent window.

## License

This project is licensed under **GNU General Public License v2.0 only**. See [`LICENSE`](LICENSE).
