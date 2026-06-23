# Slackware

> Distro id: `slackware` · Package manager: pkgtools · Search repos: Slackware `PACKAGES.TXT` (series `a`, `ap`, `d`, `k`, `kde`, `l`, `n`, `x`, `xap`, `xfce`)

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `current` |
| `15.0` |

- Default branch: `stable`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `slackware` · Default hostname: `ledit-slackware` · Default image: `ledit-slackware.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-slackware-usb.sh` |
| Configure | `backend/scripts/configure-slackware-usb.sh` |

## Host requirements

Linux: `installpkg` (pkgtools), stage tarballs, GRUB standalone EFI, `parted`, `dosfstools`, `e2fsprogs`. macOS: Docker with builder image (Alpine base).

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `SLACKWARE_RELEASE`
- Distro prefix: `SLACKWARE_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro slackware --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro slackware --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro slackware --ask-password -y

# Optional: pin a branch/release
./ledit build --distro slackware --branch stable --ask-password -y
```

Bootloader support: systemd-boot = **no** · extlinux = **no**.

## Notes

No dependency resolver: installs whole package series plus extras via `installpkg`. Configure script is a Python planner (dry-run only); builder assembles a GPT image with ext4 root + FAT32 ESP and standalone GRUB EFI.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
