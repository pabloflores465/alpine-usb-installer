# Slackware

> Distro id: `slackware` · Package manager: pkgtools · Package search: Slackware `PACKAGES.TXT` series.

## What this page covers

This page documents the `slackware` backend: supported releases, package-series behavior, build commands, generated variables, and known constraints.

## When to choose it

Choose Slackware when you want a classic pkgtools-based system and can accept less dependency automation.

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `current` |
| `15.0` |

Defaults:

- Branch/release: `stable`
- Architecture: `x86_64`; choices: `x86_64`
- User: `slackware`
- Hostname: `ledit-slackware`
- Output image name: `ledit-slackware.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `backend/scripts/build-slackware-usb.sh` |
| Configure backend | `backend/scripts/configure-slackware-usb.sh` |
| Branch environment variable | `SLACKWARE_RELEASE` |
| Distro environment prefix | `SLACKWARE_USB` |
| Shared profile prefix | `LEDIT_USB` |

Slackware package behavior is series-oriented. The backend installs selected series plus explicit extras rather than resolving dependencies in the same style as APT/DNF/Pacman.

## Host requirements

Docker Desktop on macOS using the builder image path. Native Linux requires pkgtools/installpkg-compatible tooling, GRUB standalone EFI, `parted`, `dosfstools`, and `e2fsprogs`.

## Quick commands

```sh
./ledit distros
./ledit search vim --distro slackware --branch stable --limit 5
./ledit build --distro slackware --branch stable --dry-run --ask-password -y
./ledit build --distro slackware --branch stable --ask-password -y

./ledit build --distro slackware \
  --branch stable \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-slackware.img" \
  --ask-password \
  --extra-packages "vim tmux rsync" \
  -y
```

## GUI and TUI notes

In the GUI, select **Slackware**. Package suggestions come from Slackware package indexes and package series.

In the TUI, run `./ledit tui` and select `slackware`.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want a broader Slackware package baseline. |
| `minimal` | You want to keep the image smaller and explicitly add extras. |

## Bootloader support

GRUB is supported. systemd-boot and extlinux are not supported.

## Environment variable reference

The real prefix for this backend is `SLACKWARE_USB`. The backend also receives the shared `LEDIT_USB_*` variables.

| Variable family | Meaning |
| --- | --- |
| `SLACKWARE_RELEASE` | `stable`, `current`, or `15.0`. |
| `*_PROFILE` | `compatibility` or `minimal` build preset. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Temporary secret files. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION`, `*_TILING_WMS` | Desktop/session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Services and desktop integration. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware settings. |
| `*_EXTRA_PACKAGES` | Extra Slackware package names. |

```txt
SLACKWARE_RELEASE=stable
SLACKWARE_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search differs from other distros | Slackware uses package series and `PACKAGES.TXT`; names may differ. |
| Dependency missing after boot | Add the package series or explicit package required by the workflow. |
| Bootloader validation fails | Use `--bootloader grub`. |
| Build is larger than expected | Try `--profile minimal` and fewer package series/extras. |

## Backend notes

- Slackware has no dependency resolver in the same sense as APT/DNF/Pacman.
- The builder installs selected package series plus requested extras.
- The produced image uses GPT, an ext4 root filesystem, a FAT32 ESP, and standalone GRUB EFI.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
