# Alpine Linux

> Distro id: `alpine` · Package manager: APK · Package search: Official APK repository index.

## What this page covers

This page is the operating guide for the `alpine` backend. It documents the branch choices exposed by LEDIT, the backend scripts involved, the host assumptions, the most useful CLI commands, and the environment variables the GUI/TUI/CLI generate before a build.

## When to choose it

Choose Alpine when you want a small, fast image with OpenRC and a compact package base.

## Supported branches / releases

| Branch / release |
| --- |
| `latest-stable` |
| `edge` |
| `v3.22` |
| `v3.21` |

Defaults:

- Branch/release: `latest-stable`
- Architecture: `x86_64`; choices: `x86_64`
- User: `alpine`
- Hostname: `ledit-linux`
- Output image name: `ledit.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `backend/scripts/build-alpine-usb.sh` |
| Configure backend | `backend/scripts/configure-alpine-usb.sh` |
| Branch environment variable | `ALPINE_BRANCH` |
| Distro environment prefix | `LEDIT_USB` |
| Shared profile prefix | `LEDIT_USB` |

LEDIT first normalizes CLI/GUI/TUI options into environment variables. The backend then consumes those variables to build and configure the image. Passwords are converted to temporary `*_PASSWORD_FILE` and `*_ROOT_PASSWORD_FILE` values before shell scripts run, so plain password values do not need to be passed as command-line arguments.

## Host requirements

Docker Desktop on macOS. On native Linux, the builder expects Alpine image-building tools such as `alpine-make-vm-image`, plus GRUB/EFI, `mtools`, `qemu-img`, `parted`, `dosfstools`, and `e2fsprogs`.

Cross-platform rule of thumb:

- **macOS**: use Docker Desktop for full Linux image builders and keep Docker running before starting the build.
- **Linux**: native builds need root-capable filesystem, partition, chroot, and bootloader tools.
- **Windows**: full image builds are not implemented. Use Windows only to flash an already generated image with tools such as Rufus or balenaEtcher.

## Quick commands

```sh
# See available branches and distro ids.
./ledit distros

# Search for packages in this distro's repositories.
./ledit search firefox --distro alpine --branch latest-stable --limit 5

# Validate the generated profile without creating an image.
./ledit build --distro alpine --branch latest-stable --dry-run --ask-password -y

# Build a default image.
./ledit build --distro alpine --branch latest-stable --ask-password -y

# Build with a fixed output path and extra packages.
./ledit build --distro alpine \
  --branch latest-stable \
  --image-size 24G \
  --output "$HOME/Downloads/ledit.img" \
  --ask-password \
  --extra-packages "neovim tmux docker" \
  -y
```

## GUI and TUI notes

In the GUI, select **Alpine Linux** from the distro selector. The branch/release combo updates automatically to the values listed above. Package suggestions also switch to the `APK` search backend.

In the TUI, run:

```sh
./ledit tui
```

Then pick `alpine` as the distro id.

## Build profiles

LEDIT exposes two high-level presets:

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want the broadest chance of booting on unknown hardware. This keeps firmware, networking, audio, browser, desktop defaults, and broad X11 compatibility enabled unless you override them. |
| `minimal` | You want a smaller image and are willing to explicitly add desktops, services, or packages you need. |

You can still override individual options after selecting a profile. For example:

```sh
./ledit build --distro alpine --profile minimal --desktop none --browser none --ask-password -y
```

## Bootloader support

GRUB and systemd-boot are supported. extlinux is not exposed for this backend.

Common options:

- `--bootloader grub`
- `--bootloader systemd-boot`
- `--bootloader extlinux`

If the backend does not support the requested bootloader, LEDIT fails during profile validation before running the build script.

## Environment variable reference

The real prefix for this backend is `LEDIT_USB`. Many backends also receive the shared `LEDIT_USB_*` variables for compatibility across scripts.

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

Distro-specific branch selector:

```txt
ALPINE_BRANCH=latest-stable
```

Dry-run convention:

```txt
LEDIT_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search returns nothing | Confirm the package name exists in `main`, `community` and that you selected the right branch. |
| Dry-run fails before build | Check unsupported desktop, bootloader, package, branch, or architecture values. |
| Docker build fails on macOS | Confirm Docker Desktop is running and the repo path is mounted/accessible to Docker. |
| Image builds but does not boot | Try `--bootloader grub`, keep firmware enabled, and keep `--legacy-x11-drivers` enabled for unknown hardware. |
| USB flashing is blocked | Run `./ledit devices`, verify the target is removable, and confirm the whole-disk device path, not a partition path. |

## Backend notes

- Mature backend that reuses Alpine tooling instead of trying to hand-roll the entire root filesystem.
- The configure step runs inside the image and writes OpenRC services for first boot setup.
- Auto-resize is implemented through an OpenRC first-boot service.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
