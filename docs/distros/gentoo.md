# Gentoo

> Distro id: `gentoo` · Package manager: Portage · Search repos: Portage catalogue / local eix/pkgcore (`gentoo`, `local-portage`)

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `testing` |

- Default branch: `stable`
- Default arch: `x86_64` (choices: `x86_64`, `amd64`)
- Default user: `gentoo` · Default hostname: `ledit-gentoo` · Default image: `ledit-gentoo.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-gentoo-usb.sh` |
| Configure | `backend/scripts/configure-gentoo-usb.sh` |

## Host requirements

Linux: `chroot`, stage3 tarball, `portage`, `genkernel`/initramfs, GRUB, `parted`. macOS: Docker with builder image built from `backend/docker/Dockerfile.gentoo-builder`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `GENTOO_STAGE3_BRANCH`
- Distro prefix: `GENTOO_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro gentoo --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro gentoo --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro gentoo --ask-password -y

# Optional: pin a branch/release
./ledit build --distro gentoo --branch stable --ask-password -y
```

Bootloader support: systemd-boot = **no** · extlinux = **no**.

## Notes

Stage3 bootstrap builder. Builder Docker image is `gentoo builder image` (built from `backend/docker/Dockerfile.gentoo-builder`). Configure runs inside the chroot; secrets injected via `gentoo-build.env`.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
