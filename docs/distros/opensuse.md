# openSUSE

> Distro id: `opensuse` · Package manager: Zypper · Package search: openSUSE repository metadata.

## What this page covers

This page documents the `opensuse` backend: supported release choices, host requirements, build commands, environment variables, and openSUSE-specific warnings.

## When to choose it

Choose openSUSE when you want a Zypper-based image, especially for Tumbleweed testing.

## Supported branches / releases

| Branch / release |
| --- |
| `tumbleweed` |
| `leap-16.0` |
| `leap-15.6` |

Defaults:

- Branch/release: `tumbleweed`
- Architecture: `x86_64`; choices: `x86_64`
- User: `linux`
- Hostname: `ledit-opensuse`
- Output image name: `ledit-opensuse.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/backend/scripts/build-opensuse-usb.sh` |
| Configure backend | `ledit_core/backend/scripts/configure-opensuse-usb.sh` |
| Branch environment variable | `OPENSUSE_RELEASE` |
| Distro environment prefix | `OPENSUSE_USB` |
| Shared profile prefix | `LEDIT_USB` |

LEDIT first normalizes CLI/GUI/TUI options into environment variables. The openSUSE backend consumes those variables through a Zypper installroot workflow.

## Host requirements

Docker Desktop on macOS using openSUSE containers. Native Linux requires `zypper --root`, GRUB2, `parted`, `dosfstools`, and `e2fsprogs`.

## Quick commands

```sh
./ledit distros
./ledit search firefox --distro opensuse --branch tumbleweed --limit 5
./ledit build --distro opensuse --branch tumbleweed --dry-run --ask-password -y
./ledit build --distro opensuse --branch tumbleweed --ask-password -y

./ledit build --distro opensuse \
  --branch tumbleweed \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-opensuse.img" \
  --ask-password \
  --extra-packages "vim htop curl" \
  -y
```

## GUI and TUI notes

In the GUI, select **openSUSE**. The release selector exposes Tumbleweed and Leap releases. Package suggestions use Zypper repository metadata.

In the TUI, run `./ledit tui` and select `opensuse`.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want a desktop/hardware-friendly openSUSE image. |
| `minimal` | You want a smaller Zypper installroot and will add packages manually. |

## Bootloader support

GRUB and systemd-boot are supported by the profile layer. extlinux is not supported.

## Environment variable reference

The real prefix for this backend is `OPENSUSE_USB`. The backend also receives the shared `LEDIT_USB_*` variables.

| Variable family | Meaning |
| --- | --- |
| `OPENSUSE_RELEASE` | Selected openSUSE release. |
| `*_PROFILE` | `compatibility` or `minimal` build preset. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Temporary secret files. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION`, `*_TILING_WMS` | Desktop/session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Services and desktop integration. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware settings. |
| `*_EXTRA_PACKAGES` | Extra Zypper package names. |

```txt
OPENSUSE_RELEASE=tumbleweed
OPENSUSE_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search returns nothing | Confirm the package exists for the selected Tumbleweed/Leap release. |
| Full build fails | Validate with dry-run first and test on Linux if Docker path is unreliable. |
| Image builds but boot is inconsistent | Treat full images as experimental until boot-tested on target hardware. |
| Bootloader validation fails | Try `--bootloader grub`. |

## Backend notes

- This backend uses a Zypper installroot foundation.
- Dry-run and package search are the safest validation paths.
- Treat full images as experimental until you have boot-tested them on your target hardware.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
