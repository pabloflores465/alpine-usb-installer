# Alpine USB Installer

Tool for building and flashing a bootable, preinstalled Alpine Linux x86_64 USB image.

It started as an XFCE-only builder, but now the GUI and build scripts expose a full configurable Alpine profile: desktop environment, tiling/window managers, Wi‑Fi, Bluetooth, display manager, bootloader, kernel flavor, keyboard/language, users, firmware, audio and extra APK packages.

## What it can configure

Defaults are safe and match the original experience: `linux-lts`, GRUB removable UEFI, XFCE, LightDM, NetworkManager + Wi‑Fi, Bluetooth, PipeWire, Firefox ESR, user `pablo` / password `pablo`, English locale and Latin American Spanish keyboard.

`Image size` is the minimum build image size, not the final used space limit. By default the installed USB auto-expands the root partition/filesystem on first boot to use the full target USB drive.

Configurable sections in the Qt app are collapsed by default:

- System, user and localization:
  - minimum image size, Alpine branch, hostname, user/passwords
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
  - first-boot root filesystem expansion to fill the USB drive
- Extra packages:
  - arbitrary additional `apk add` package names
  - package search against Alpine's official `main` + `community` APK indexes
  - top 10 package suggestions with one-click/double-click add; multiple packages can still be typed manually separated by spaces

The generated image is meant to be written directly to a USB drive and booted as an installed Alpine system.

## Compatibility fixes

- Polkit: desktop packages are installed after `polkit-elogind` is explicitly installed, so APK does not accidentally choose the non-elogind `polkit` provider when packages such as `xfce-polkit`, GNOME, Plasma, MATE or LXQt pull a polkit agent.
- Lightweight WMs: the generated system installs a duplicate-safe polkit agent launcher for sessions such as i3, Sway, bspwm, Openbox and labwc.
- Bluetooth: the installer uses `obexd-enhanced` instead of `bluez-obexd`, avoiding the GNOME Bluetooth conflict while still providing the OBEX service.
- Keyboard: Alpine's current OpenRC console keymap service is `loadkeys`; the generated system writes `/etc/conf.d/loadkeys` and keeps `/etc/conf.d/keymaps` for compatibility.
- USB capacity: the root partition is expanded on first boot with `cloud-utils-growpart` + `resize2fs`, so a 16G image flashed to a 64G USB uses the full 64G after boot.
- systemd-boot display mode: generated `loader.conf` sets `console-mode max` by default. This makes systemd-boot switch the UEFI framebuffer to the highest available mode before Linux starts, matching the initial resolution behavior seen with GRUB on systems that rely on EFI/simpledrm framebuffer.

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
- choose the minimum image size used during build
- open collapsed configuration sections and customize the profile
- search official Alpine packages in the Extra APK packages section and add one or several suggestions
- build the image
- select a target USB drive
- flash the image

If the selector does not detect your USB drive, you can type the device manually, for example `/dev/disk7` on macOS or `/dev/sdb` on Linux.

Supported flashing helpers:

- macOS: `diskutil`, `dd`, administrator password prompt
- Linux: `lsblk`, `dd`, `sudo`/`pkexec`
- Windows: raw flashing is not implemented; use Rufus/balenaEtcher with the generated image

## TUI and CLI

For a complete interactive terminal experience, use the curses TUI:

```sh
./run_tui.sh
# or:
./run_cli.sh tui
```

The TUI includes full-screen menus for all installer options, package search, build/dry-run, USB device selection, flashing, and host diagnostics. It always allows manual USB device entry if automatic detection finds nothing.

The project also includes a fast dependency-free CLI with the same build options as the GUI:

```sh
./run_cli.sh --help
./run_cli.sh build --help
```

Useful CLI commands:

```sh
# Open the full TUI
./run_cli.sh tui

# Search official Alpine packages and show the top 10 suggestions
./run_cli.sh search firefox

# Validate a profile without building the image
./run_cli.sh build --dry-run --desktop xfce --bootloader systemd-boot

# Build without interactive confirmation
./run_cli.sh build --desktop plasma --display-manager sddm --bootloader systemd-boot -y

# List removable USB devices
./run_cli.sh devices

# Flash an image to USB; requires typing ERASE unless -y is passed
./run_cli.sh flash alpine-usb.img /dev/sdX
```

The `build` subcommand exposes the same profile controls as the GUI: desktop, display manager, WMs, Wi‑Fi, Bluetooth, bootloader, kernel, firmware, keyboard/language, user/passwords, image size, auto-resize, browser/audio and extra APK packages. Extra packages can be repeated:

```sh
./run_cli.sh build --extra-package neovim --extra-package "tmux htop" --extra-package docker
```

## CLI build examples

Default profile:

```sh
IMAGE_SIZE=16G ./build-alpine-usb.sh
# or:
./run_cli.sh build -y
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

By default, if you flash this image to a larger USB drive, Alpine grows the root partition/filesystem on first boot to fill the drive. Disable it with:

```sh
ALPINE_USB_AUTO_RESIZE=0 ./build-alpine-usb.sh
```

For systemd-boot, the installer defaults to the highest UEFI console mode so the initial framebuffer resolution is not stuck at a low firmware mode:

```sh
ALPINE_USB_SYSTEMD_BOOT_CONSOLE_MODE=max ./build-alpine-usb.sh
```

Valid values are `max`, `auto`, `keep` or a numeric UEFI console mode.

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

Use the whole disk (`/dev/sdX`, `/dev/diskX`), not a partition (`/dev/sdX1`). Do not copy `alpine-usb.img` as a file onto a FAT/exFAT USB; it must be written raw to the whole device.

## Booting the USB

General boot steps:

1. Shut down the target computer.
2. Insert the flashed USB drive.
3. Open the one-time boot menu during power-on. Common keys are `F12`, `F9`, `F8`, `F11`, `Esc` or `Del` depending on vendor.
4. Choose the USB drive entry.
5. If the machine shows both `UEFI: <usb name>` and a non-UEFI/legacy USB entry, try the one matching your firmware setup:
   - Modern machines: usually `UEFI: <usb name>`.
   - Older BIOS/CSM machines: usually the non-UEFI `USB Hard Drive` entry.

Recommended firmware settings when a USB does not boot:

- Enable `USB Boot`.
- Disable `Secure Boot` unless you know your firmware accepts this image.
- Disable `Fast Boot` if the USB is skipped.
- For older laptops/desktops, enable `Legacy Support`, `CSM` or `Legacy Boot` and try the non-UEFI USB entry.
- Put `USB Hard Drive` or `Removable USB` above the internal disk in boot order if using permanent boot order instead of a one-time menu.
- Try another USB port. Older machines often boot more reliably from USB 2.0 ports than USB 3.0 ports.
- Reflash the image to the whole disk if the USB only shows files or does not appear in the boot menu.

Common vendor boot-menu keys:

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
| Apple Intel Mac | hold `Option` | N/A |

### Intel Macs

Intel Macs can boot the generated `x86_64` image. Apple Silicon Macs can build and flash the image, but cannot boot this x86_64 Alpine image natively.

Recommended profile for Intel Macs:

- `Arch`: `x86_64`
- `Bootloader`: `GRUB`
- `Kernel`: `linux-lts`
- `Firmware`: full firmware enabled
- `Desktop`: `XFCE`
- `Display manager`: `LightDM`
- `Network`: `NetworkManager`
- `Wi-Fi`: enabled
- `Bluetooth`: enabled
- `Auto-resize USB`: enabled

Flash from macOS with the GUI or manually:

```sh
diskutil list
diskutil unmountDisk /dev/diskX
sudo dd if=alpine-usb.img of=/dev/rdiskX bs=4m status=progress
sync
diskutil eject /dev/diskX
```

Use the whole raw disk (`/dev/rdiskX`), not a partition such as `/dev/diskXs1`.

Boot steps:

1. Shut down the Mac.
2. Insert the flashed USB drive.
3. Power on while holding `Option` / `Alt`.
4. In the Apple boot picker, choose `EFI Boot` or the orange USB icon.
5. Press Enter.

If the USB does not appear:

- Try another USB port.
- Try a simple USB 2.0 hub on older Macs.
- Reflash the image raw to the whole disk.
- Use `GRUB` instead of `systemd-boot`.
- For Macs with the Apple T2 security chip, allow external boot in Recovery.

T2 Intel Mac external boot setup:

1. Boot macOS Recovery with `Cmd` + `R`.
2. Open `Utilities` → `Startup Security Utility`.
3. Set `Secure Boot` to `No Security` if needed.
4. Set `External Boot` to `Allow booting from external media`.
5. Reboot while holding `Option` / `Alt` and choose the USB.

### HP ProBook 4440s / older HP laptops

The HP ProBook 4440s is an older BIOS/UEFI hybrid laptop. If the USB does not boot:

1. Power on and press `Esc` repeatedly.
2. Press `F10` for BIOS Setup.
3. Open `System Configuration` → `Boot Options`.
4. Set:
   - `USB Boot`: enabled
   - `Secure Boot`: disabled
   - `Legacy Support`: enabled
   - `Fast Boot`: disabled, if present
5. Move `USB Hard Drive` / `USB Diskette on Key` above the internal disk, or use one-time boot.
6. Save with `F10`.
7. Reboot, press `Esc`, then `F9`.
8. Pick the non-UEFI `USB Hard Drive` entry first. If it fails, try the `UEFI: USB` entry.

For this class of hardware, the most reliable profile is usually `XFCE`, `LightDM`, `GRUB`, `linux-lts`, firmware enabled, NetworkManager enabled, Wi-Fi enabled, and auto-resize enabled.

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
