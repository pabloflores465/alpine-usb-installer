# Alpine USB XFCE Builder

Tool for building a bootable Alpine Linux x86_64 USB image with a preconfigured XFCE desktop.

The generated image is meant to be written directly to a USB drive and booted as an installed Alpine system, not just as a basic installer.

## Status

This software is under active development. The configuration may change as Alpine versions, hardware support, drivers, display managers, and real-world testing evolve.

## What it configures

- Alpine Linux `latest-stable`
- Removable USB UEFI boot support (`/EFI/BOOT/BOOTX64.EFI`)
- XFCE
- LightDM + `lightdm-gtk-greeter`
- English system language + Latin American Spanish keyboard layout (`latam`)
- Initial user `pablo`
- `sudo` and `doas`
- D-Bus, elogind, polkit, eudev, seatd
- NetworkManager + Wi-Fi (`wpa_supplicant`, Linux firmware)
- PipeWire audio
- Firefox ESR
- Common input/video support:
  - `xf86-input-libinput`
  - AMDGPU/ATI/Intel/Nouveau/VESA/FBDEV
- USB-friendly optimizations:
  - `tmpfs` for `/tmp` and `/var/tmp`
  - lower swappiness
  - fewer APK cache writes
  - `noatime` where applicable

## Requirements

Building is recommended on Linux or Docker Desktop with NBD support.

On macOS, Docker Desktop may work better than Colima for this workflow because the build uses `qemu-nbd`.

On native Linux you also need `mtools` and `grub-efi`/`grub-mkstandalone` to install the removable UEFI bootloader into the EFI partition.

Python GUI dependencies are listed in `requirements.txt`. The helper script creates its own `.qtvenv` automatically if needed.

## Quick USB flashing GUI

The repository includes a simple cross-platform graphical utility to select an image and write it to a USB drive.

Qt GUI:

```sh
./run_qt_gui.sh
```

From the GUI you can:

- build the image (`Build image`)
- select the image size (`16G`, `32G`, etc.)
- select the target USB drive
- write the image (`Flash USB`)

On macOS, `Build image` uses Docker Desktop because the build requires Linux/NBD.

If the selector does not detect your USB drive, you can type the device manually, for example `/dev/disk7` on macOS or `/dev/sdb` on Linux.

Support:

- macOS: uses `diskutil`, `dd`, and asks for administrator permissions.
- Linux: uses `lsblk`, `dd`, and `sudo`/`pkexec` when needed.
- Windows: raw flashing is not implemented yet for safety; use Rufus/balenaEtcher with the generated image.

## Build the image

```sh
chmod +x build-alpine-usb.sh configure-alpine-usb.sh
IMAGE_SIZE=16G ./build-alpine-usb.sh
```

Result:

```txt
alpine-usb-xfce.img
```

## Write to USB

⚠️ This completely erases the target device.

On macOS:

```sh
diskutil unmountDisk /dev/diskX
sudo dd if=alpine-usb-xfce.img of=/dev/rdiskX bs=4M status=progress
sync
diskutil eject /dev/diskX
```

On Linux:

```sh
lsblk
sudo dd if=alpine-usb-xfce.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Use the whole disk (`/dev/sdX`, `/dev/diskX`), not a partition (`/dev/sdX1`).

## Initial login

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

## Notes

- The generated image is not included in the repository.
- The repository contains the scripts needed to reproduce the image.
- If LightDM fails, XFCE can be started manually with:

```sh
startx /usr/bin/startxfce4
```

## License

MIT
