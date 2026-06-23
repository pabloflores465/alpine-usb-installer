# Arch Linux

> Distro id: `arch` · Package manager: Pacman · Package search: Arch package API.

## What this page covers

This page is the operating guide for the `arch` backend. It documents the branch choices exposed by LEDIT, the backend scripts involved, the host assumptions, the most useful CLI commands, and the environment variables the GUI/TUI/CLI generate before a build.

## When to choose it

Choose Arch when you want a rolling-release image with current desktop packages and Pacman.

## Supported branches / releases

| Branch / release |
| --- |
| `rolling` |
| `stable` |

Defaults:

- Branch/release: `rolling`
- Architecture: `x86_64`; choices: `x86_64`
- User: `arch`
- Hostname: `ledit-arch`
- Output image name: `ledit-arch.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `backend/scripts/build-arch-usb.sh` |
| Configure backend | `backend/scripts/configure-arch-usb.sh` |
| Branch environment variable | `ARCH_USB_BRANCH` |
| Distro environment prefix | `ARCH_USB` |
| Shared profile prefix | `LEDIT_USB` |

LEDIT first normalizes CLI/GUI/TUI options into environment variables. The backend then consumes those variables to build and configure the image. Passwords are converted to temporary `*_PASSWORD_FILE` and `*_ROOT_PASSWORD_FILE` values before shell scripts run, so plain password values do not need to be passed as command-line arguments.

## Host requirements

Docker Desktop on macOS using `archlinux:latest`. On native Linux, install Arch build tooling such as `pacstrap`/`arch-install-scripts`, GRUB/systemd boot tooling, `parted`, `dosfstools`, and `e2fsprogs`.

Cross-platform rule of thumb:

- **macOS**: use Docker Desktop for full Linux image builders and keep Docker running before starting the build.
- **Linux**: native builds need root-capable filesystem, partition, chroot, and bootloader tools.
- **Windows**: full image builds are not implemented. Use Windows only to flash an already generated image with tools such as Rufus or balenaEtcher.

## Quick commands

```sh
./ledit distros
./ledit search firefox --distro arch --branch rolling --limit 5
./ledit build --distro arch --branch rolling --dry-run --ask-password -y
./ledit build --distro arch --branch rolling --ask-password -y

./ledit build --distro arch \
  --branch rolling \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-arch.img" \
  --ask-password \
  --extra-packages "neovim tmux docker" \
  -y
```

## GUI and TUI notes

In the GUI, select **Arch Linux** from the distro selector. The branch/release combo updates automatically to the values listed above. Package suggestions also switch to the `Pacman` search backend.

In the TUI, run:

```sh
./ledit tui
```

Then pick `arch` as the distro id.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want the broadest chance of booting on unknown hardware. |
| `minimal` | You want a smaller image and will explicitly add packages/services. |

Example:

```sh
./ledit build --distro arch --profile minimal --desktop none --browser none --ask-password -y
```

## Bootloader support

GRUB and systemd-boot are supported. extlinux is not supported.

If the backend does not support the requested bootloader, LEDIT fails during profile validation before running the build script.

## Environment variable reference

The real prefix for this backend is `ARCH_USB`. The backend also receives the shared `LEDIT_USB_*` variables.

| Variable family | Meaning |
| --- | --- |
| `*_PROFILE` | `compatibility` or `minimal` build preset. |
| `*_USER`, `*_HOSTNAME` | Initial local username and host identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Temporary secret files used instead of exposing passwords in shell arguments. |
| `*_TIMEZONE`, `*_LOCALE`, `*_LANGUAGE` | Locale and language settings. |
| `*_CONSOLE_KEYMAP`, `*_XKB_LAYOUT`, `*_XKB_VARIANT`, `*_XKB_MODEL` | Console and graphical keyboard settings. |
| `*_DESKTOP`, `*_TILING_WMS`, `*_DEFAULT_SESSION`, `*_DISPLAY_MANAGER` | Graphical session selection. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Desktop integration services. |
| `*_FIRMWARE`, `*_LEGACY_X11_DRIVERS`, `*_KERNEL_FLAVOR` | Hardware compatibility choices. |
| `*_BOOTLOADER`, `*_BOOT_TIMEOUT`, `*_SYSTEMD_BOOT_CONSOLE_MODE` | Boot behavior. |
| `*_AUTO_RESIZE` | Enable first-boot root filesystem expansion when supported. |
| `*_EXTRA_PACKAGES` | Space-separated list of distro-native packages. |

```txt
ARCH_USB_BRANCH=rolling
ARCH_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search returns nothing | Confirm the package name exists in `core`, `extra`, or `multilib`. |
| Docker tries to pull a package name as an image | Pull latest; the backend now passes env values via `--env-file`. |
| Dry-run fails before build | Check unsupported desktop, bootloader, package, branch, or architecture values. |
| Image builds but does not boot | Try `--bootloader grub`, keep firmware enabled, and keep `--legacy-x11-drivers` enabled. |

## Backend notes

- The builder is pacstrap-based.
- `stable` is accepted as an alias for the rolling branch exposed by the provider.
- Docker environment values are passed through `--env-file`, so multi-word extra package lists do not split into Docker positionals.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
