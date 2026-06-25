# NixOS

> Distro id: `nixos` · Package manager: nixpkgs · Package search: nixpkgs.

## What this page covers

This page documents the `nixos` backend. NixOS is different from the shell-script distros because LEDIT renders Nix configuration and builds through the Python NixOS backend instead of a distro shell script.

## When to choose it

Choose NixOS when you want a declarative USB image generated from rendered Nix configuration.

## Supported branches / releases

| Branch / release |
| --- |
| `nixos-24.11` |
| `nixos-25.05` |
| `nixos-unstable` |

Defaults:

- Branch/release: `nixos-24.11`
- Architecture: `x86_64-linux`; choices: `x86_64-linux`, `x86_64`
- User: `nixos`
- Hostname: `ledit-nixos`
- Output image name: `ledit-nixos.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/nixos/build.py` |
| Configure backend | `none; configuration is rendered as Nix files` |
| Branch environment variable | `NIXOS_CHANNEL` |
| Distro environment prefix | `NIXOS_USB` |
| Shared profile prefix | `LEDIT_USB` |

NixOS does not use `ledit_core/backend/scripts/build-*.sh`. LEDIT converts the selected profile into Nix configuration, validates/render it during dry-run, and then builds using the NixOS image path.

## Host requirements

Install Nix and `nixos-generate` on a supported build host, or use the Docker-backed path when available. macOS users should prefer the Docker path.

## Quick commands

```sh
./ledit distros
./ledit search firefox --distro nixos --branch nixos-24.11 --limit 5
./ledit build --distro nixos --branch nixos-24.11 --dry-run --ask-password -y
./ledit build --distro nixos --branch nixos-24.11 --ask-password -y

./ledit build --distro nixos \
  --branch nixos-25.05 \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-nixos.img" \
  --ask-password \
  --extra-packages "vim tmux git" \
  -y
```

## GUI and TUI notes

In the GUI, select **NixOS**. The branch selector maps to NixOS channels. Package suggestions use nixpkgs.

In the TUI, run `./ledit tui` and select `nixos`.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want a graphical/hardware-friendly default config. |
| `minimal` | You want a smaller declarative baseline. |

## Bootloader support

The NixOS sd-image path uses extlinux. GRUB and systemd-boot are not the validated LEDIT path here.

## Environment variable reference

The real prefix for this backend is `NIXOS_USB`.

| Variable family | Meaning |
| --- | --- |
| `NIXOS_CHANNEL` | Selected NixOS channel. |
| `*_PROFILE` | `compatibility` or `minimal` build preset. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Temporary secret files. |
| `*_TIMEZONE`, `*_LOCALE`, `*_LANGUAGE` | Locale and language settings. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION`, `*_TILING_WMS` | Desktop/session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Services and desktop integration. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware settings. |
| `*_EXTRA_PACKAGES` | Extra nixpkgs package names. |

```txt
NIXOS_CHANNEL=nixos-24.11
NIXOS_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Dry-run renders config but build fails | Check Nix/nixos-generate availability and host permissions. |
| Package search returns nothing | Try the nixpkgs attribute name rather than a distro package name. |
| Bootloader validation fails | Use the default NixOS sd-image path; extlinux is expected here. |
| Build is very large | Try `--profile minimal`, `--desktop none`, and `--browser none`. |

## Backend notes

- NixOS does not use a shell build script.
- Dry-run renders the generated configuration instead of running a distro configure script.
- GUI build support is handled through the dedicated NixOS backend rather than the generic script runner.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
