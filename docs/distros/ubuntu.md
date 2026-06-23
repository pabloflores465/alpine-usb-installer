# Ubuntu

> Distro id: `ubuntu` · Package manager: APT · Search repos: APT / `apt-cache` (`main`, `universe`, `multiverse`)

## Supported branches / releases

| Branch / release |
| --- |
| `24.04` |
| `noble` |
| `22.04` |
| `jammy` |

- Default branch: `24.04`
- Default arch: `x86_64` (choices: `x86_64`, `amd64`)
- Default user: `ubuntu` · Default hostname: `ledit-ubuntu` · Default image: `ledit-ubuntu.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-ubuntu-usb.sh` |
| Configure | `backend/scripts/configure-ubuntu-usb.sh` |

## Host requirements

Linux: `debootstrap`, `grub-install`, `parted`, `dosfstools`, `e2fsprogs`, `sudo`. macOS: Docker with `ubuntu:24.04`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `UBUNTU_RELEASE`
- Distro prefix: `UBUNTU_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro ubuntu --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro ubuntu --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro ubuntu --ask-password -y

# Optional: pin a branch/release
./ledit build --distro ubuntu --branch 24.04 --ask-password -y
```

Bootloader support: systemd-boot = **yes (package selection mapped; GRUB install is the validated path)** · extlinux = **no**.

## Notes

debootstrap-based builder for Noble (24.04) and Jammy (22.04). Configure runs inside the target root. See `docs/ubuntu-support.md` for detailed status.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
