# RHEL family (Rocky/Alma/CentOS Stream compatible)

> Distro id: `rhel` · Package manager: DNF · Search repos: DNF repoquery (`baseos`, `appstream`)

## Supported branches / releases

| Branch / release |
| --- |
| `9` |
| `10` |

- Default branch: `9`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `linux` · Default hostname: `ledit-rhel` · Default image: `ledit-rhel.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-rhel-usb.sh` |
| Configure | `backend/scripts/configure-rhel-usb.sh` |

## Host requirements

Linux: `dnf --installroot`, `grub2-efi-x64`, `grub2-tools`, `parted`, `dosfstools`, `e2fsprogs`. macOS: Docker with `rockylinux:9`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `RHEL_USB_RELEASE`
- Distro prefix: `RHEL_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro rhel --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro rhel --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro rhel --ask-password -y

# Optional: pin a branch/release
./ledit build --distro rhel --branch 9 --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

Aliases `rocky`, `alma`, `centos`, `centos-stream` resolve to `rhel`; `RHEL_USB_DISTRO` sets the variant. Package list resolved by `ledit_core/rhel_packages/packages.py`. A `linux-usb-firstboot` service auto-grows root.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
