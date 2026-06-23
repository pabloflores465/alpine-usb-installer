# Arch Linux

> Distro id: `arch` · Package manager: Pacman · Search repos: Arch package API (`core`, `extra`, `multilib`)

## Supported branches / releases

| Branch / release |
| --- |
| `rolling` |
| `stable alias` |

- Default branch: `rolling`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `arch` · Default hostname: `ledit-arch` · Default image: `ledit-arch.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-arch-usb.sh` |
| Configure | `backend/scripts/configure-arch-usb.sh` |

## Host requirements

Linux: `pacstrap`, `arch-install-scripts`, `grub`, `efibootmgr`, `systemd`, `parted`, `dosfstools`, `e2fsprogs`. macOS: Docker with `archlinux:latest`.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `ARCH_USB_BRANCH`
- Distro prefix: `ARCH_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro arch --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro arch --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro arch --ask-password -y

# Optional: pin a branch/release
./ledit build --distro arch --branch rolling --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

Pacstrap-based builder. `configure-arch-usb.sh` is a Python planner that validates the package set and writes `.work/arch-packages.txt` / `.work/arch-config.env`; env passed via `--env-file` to keep spaced `LEDIT_USB_EXTRA_PACKAGES` intact.

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
