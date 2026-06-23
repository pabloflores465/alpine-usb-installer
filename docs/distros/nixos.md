# NixOS

> Distro id: `nixos` · Package manager: nixpkgs · Search repos: `nix search` / nixpkgs (`nixpkgs`)

## Supported branches / releases

| Branch / release |
| --- |
| `nixos-24.11` |
| `nixos-25.05` |
| `nixos-unstable` |

- Default branch: `nixos-24.11`
- Default arch: `x86_64-linux` (choices: `x86_64-linux`, `x86_64`)
- Default user: `nixos` · Default hostname: `ledit-nixos` · Default image: `ledit-nixos.img`

## Backend scripts

| Script | Path |
| --- | --- |
| Build | `Python backend (`ledit_core/nixos/build.py`)` |
| Configure | `none` |

## Host requirements

Linux: `nix`, `nixos-generate` (or the Docker build path). macOS: Docker path recommended.

## Environment variables

The provider writes both the distro-specific prefix and the shared `LEDIT_USB` prefix (when they differ). Secrets are written to `*_PASSWORD_FILE`/`*_ROOT_PASSWORD_FILE` instead of passing plain values to the shell.

- Branch/release env: `NIXOS_CHANNEL`
- Distro prefix: `NIXOS_USB`
- Shared profile prefix: `LEDIT_USB_*` (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile)
- Dry-run flag: `{distro_prefix}_DRY_RUN=1` (and `LEDIT_USB_DRY_RUN=1` when distro prefix differs)

## Usage

```sh
# Dry-run (no image created; works on macOS too)
./ledit build --distro nixos --dry-run --ask-password -y

# Search packages
./ledit search firefox --distro nixos --limit 5

# Full build (native Linux or Docker on macOS)
./ledit build --distro nixos --ask-password -y

# Optional: pin a branch/release
./ledit build --distro nixos --branch nixos-24.11 --ask-password -y
```

Bootloader support: systemd-boot = **no (sd-image uses extlinux)** · extlinux = **yes**.

## Notes

No shell build script. `ledit_core/nixos/build.py` renders `configuration.nix`/`flake.nix` from `NIXOS_USB_*` env and builds via `nixos-generate` or Docker. Dry-run renders config without building. GUI build worker uses the dedicated NixOS runner (not the script runner).

## See also

- [Per-distro backends index](README.md)
- [Project README](../../README.md)
