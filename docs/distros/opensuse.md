# openSUSE

> Distro id: `opensuse` · Package manager: Zypper · Search repos: Zypper repository metadata (`oss`)

## Supported branches / releases

| Branch / release |
| --- |
| `tumbleweed` |
| `leap-16.0` |
| `leap-15.6` |

- Default branch: `tumbleweed`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `linux` · Default hostname: `ledit-opensuse` · Default image: `ledit-opensuse.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-opensuse-usb.sh` |
| Configure | `backend/scripts/configure-opensuse-usb.sh` |

## Host requirements

Linux: `zypper --root`, `grub2`, `parted`, `dosfstools`, `e2fsprogs`. macOS: Docker with `opensuse/tumbleweed`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `OPENSUSE_RELEASE`
- Distro prefix: `OPENSUSE_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro opensuse --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro opensuse --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro opensuse --ask-password -y

# Optional: pin a branch/release
./ledit build --distro opensuse --branch tumbleweed --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

Experimental `zypper --root` installroot foundation. Dry-run and package search are reliable; full produced images should be validated manually before flashing.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
