# Fedora

> Distro id: `fedora` · Package manager: DNF · Search repos: DNF repoquery (`fedora`, `updates`)

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `latest` |
| `rawhide` |
| `42` |
| `41` |

- Default branch: `stable`
- Default arch: `x86_64` (choices: `x86_64`)
- Default user: `fedora` · Default hostname: `ledit-fedora` · Default image: `ledit-fedora.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `backend/scripts/build-fedora-usb.sh` |
| Configure | `none (build script is also the dry-run validator)` |

## Host requirements

Linux: `dnf`, `parted`, `dosfstools`, `e2fsprogs`, `grub2-efi-x64`, `grub2-tools`. macOS: full image creation is Linux-only in this adapter; use dry-run and package search on macOS.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `FEDORA_RELEASE`
- Distro prefix: `FEDORA_USB (shared: LEDIT_USB)`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro fedora --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro fedora --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro fedora --ask-password -y

# Optional: pin a branch/release
./ledit build --distro fedora --branch stable --ask-password -y
```

Bootloader support: systemd-boot = **yes** · extlinux = **no**.

## Notes

Plan-based builder: `ledit_core/linux_distros/fedora.py` computes packages/groups/services/target from options and writes `FEDORA_USB_*` plan env vars. Dry-run prints the rendered plan (`FEDORA_USB_PACKAGES`, `FEDORA_USB_GROUPS`, `FEDORA_USB_SERVICES`).

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
