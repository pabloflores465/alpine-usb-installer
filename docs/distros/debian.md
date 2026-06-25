# Debian

> Distro id: `debian` · Package manager: APT · Package search: Debian APT repositories.

## What this page covers

This page is the operating guide for the `debian` backend. It documents the branch choices exposed by LEDIT, the backend scripts involved, the host assumptions, the most useful CLI commands, and the environment variables the GUI/TUI/CLI generate before a build.

## When to choose it

Choose Debian when you want a conservative, familiar APT-based USB image.

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `testing` |
| `sid` |
| `trixie` |
| `bookworm` |
| `forky` |

Defaults:

- Branch/release: `stable`
- Architecture: `amd64`; choices: `amd64`, `x86_64`
- User: `debian`
- Hostname: `ledit-debian`
- Output image name: `ledit-debian.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/backend/scripts/build-debian-usb.sh` |
| Configure backend | `ledit_core/backend/scripts/configure-debian-usb.sh` |
| Branch environment variable | `DEBIAN_RELEASE` |
| Distro environment prefix | `DEBIAN_USB` |
| Shared profile prefix | `LEDIT_USB` |

LEDIT first normalizes CLI/GUI/TUI options into environment variables. The backend then consumes those variables to build and configure the image. Passwords are converted to temporary `*_PASSWORD_FILE` and `*_ROOT_PASSWORD_FILE` values before shell scripts run, so plain password values do not need to be passed as command-line arguments.

## Host requirements

Docker Desktop on macOS using a Debian container path. On native Linux, install `debootstrap`, GRUB install tools, `parted`, `dosfstools`, `e2fsprogs`, and `sudo`.

Cross-platform rule of thumb:

- **macOS**: use Docker Desktop for full Linux image builders and keep Docker running before starting the build.
- **Linux**: native builds need root-capable filesystem, partition, chroot, and bootloader tools.
- **Windows**: full image builds are not implemented. Use Windows only to flash an already generated image with tools such as Rufus or balenaEtcher.

## Quick commands

```sh
./ledit distros
./ledit search firefox --distro debian --branch stable --limit 5
./ledit build --distro debian --branch stable --dry-run --ask-password -y
./ledit build --distro debian --branch stable --ask-password -y

./ledit build --distro debian \
  --branch stable \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-debian.img" \
  --ask-password \
  --extra-packages "vim htop curl" \
  -y
```

## GUI and TUI notes

In the GUI, select **Debian** from the distro selector. The branch/release combo updates automatically to the values listed above. Package suggestions also switch to the `APT` search backend.

In the TUI, run `./ledit tui` and pick `debian` as the distro id.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want broad desktop and hardware defaults. |
| `minimal` | You want a small base and will add packages manually. |

```sh
./ledit build --distro debian --profile minimal --desktop none --browser none --ask-password -y
```

## Bootloader support

GRUB and systemd-boot are supported. extlinux is not supported.

## Environment variable reference

The real prefix for this backend is `DEBIAN_USB`. The backend also receives the shared `LEDIT_USB_*` variables.

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
DEBIAN_RELEASE=stable
DEBIAN_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search returns nothing | Confirm the package exists in the selected Debian suite. |
| Dry-run fails before build | Check branch, architecture, bootloader, or package names. |
| Docker build fails on macOS | Confirm Docker Desktop is running and the output directory is shared. |
| Image builds but does not boot | Try GRUB first and keep firmware enabled. |

## Backend notes

- The builder is debootstrap-based.
- The configure script runs inside the target root through chroot.
- When distro-specific password variables are absent, the backend falls back to the shared LEDIT password file variables.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
