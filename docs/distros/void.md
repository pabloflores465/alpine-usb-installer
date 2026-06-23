# Void Linux (glibc)

> Distro id: `void` · Package manager: XBPS · Search repos: XBPS repositories (`current`)

## Supported branches / releases

| Branch / release |
| --- |
| `current` |
| `glibc` |

- Default branch: `current`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `void` · Default hostname: `ledit-void` · Default image: `ledit-void.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-void-usb.sh` |
| Configure | `backend/scripts/configure-void-usb.sh` |

## Host requirements

Linux: `xbps-install -r`, `grub`, `parted`, `dosfstools`, `e2fsprogs`. macOS: Docker with `ghcr.io/void-linux/void-glibc-full:latest`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `VOID_REPOSITORY`
- Distro prefix: `VOID_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro void --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro void --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro void --ask-password -y

# Optional: pin a branch/release
./ledit build --distro void --branch current --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

`xbps-install -r` installroot builder. Configure runs inside the mounted target via chroot; `VOID_USB_EXTRA_PACKAGES` and `LEDIT_USB_EXTRA_PACKAGES` both accepted.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
