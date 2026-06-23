# Debian

> Distro id: `debian` · Package manager: APT · Search repos: APT / `apt-cache`

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `testing` |
| `sid` |
| `trixie` |
| `bookworm` |
| `forky` |

- Default branch: `stable`
- Default arch: `amd64` (choices: `amd64`, `x86_64`)
- Default user: `debian` · Default hostname: `ledit-debian` · Default image: `ledit-debian.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-debian-usb.sh` |
| Configure | `backend/scripts/configure-debian-usb.sh` |

## Host requirements

Linux: `debootstrap`, `grub-install`, `parted`, `dosfstools`, `e2fsprogs`, `sudo`. macOS: Docker with `debian:stable-slim`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `DEBIAN_RELEASE`
- Distro prefix: `DEBIAN_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro debian --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro debian --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro debian --ask-password -y

# Optional: pin a branch/release
./ledit build --distro debian --branch stable --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

debootstrap-based builder. Configure script runs inside the target root via chroot. Falls back to `LEDIT_USB_PASSWORD_FILE`/`LEDIT_USB_ROOT_PASSWORD_FILE` when `DEBIAN_USB_*` are not set.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
