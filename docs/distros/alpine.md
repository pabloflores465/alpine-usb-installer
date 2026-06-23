# Alpine Linux

> Distro id: `alpine` · Package manager: APK · Search repos: `main`, `community`

## Supported branches / releases

| Branch / release |
| --- |
| `latest-stable` |
| `edge` |
| `v3.22` |
| `v3.21` |

- Default branch: `latest-stable`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `alpine` · Default hostname: `ledit-linux` · Default image: `ledit.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-alpine-usb.sh` |
| Configure | `backend/scripts/configure-alpine-usb.sh` |

## Host requirements

macOS: Docker Desktop. Linux: `apk`, `alpine-make-vm-image`, GRUB/EFI, `mtools`, `qemu-img`, `parted`, `dosfstools`, `e2fsprogs`, `multipath-tools`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `ALPINE_BRANCH`
- Distro prefix: `LEDIT_USB`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro alpine --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro alpine --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro alpine --ask-password -y

# Optional: pin a branch/release
./ledit build --distro alpine --branch latest-stable --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no (use grub or systemd-boot)**.

## Notes

Mature builder reusing `alpine-make-vm-image`; builds an APK repo list and `configure-alpine-usb.sh` runs inside the image via OpenRC. Bootloader GRUB or systemd-boot. Auto-grow root on first boot via an OpenRC service.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
