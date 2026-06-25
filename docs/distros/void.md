# Void Linux (glibc)

> Distro id: `void` · Package manager: XBPS · Package search: XBPS current repositories.

## What this page covers

This page documents the `void` backend: repository choices, XBPS installroot workflow, commands, generated variables, and Void-specific notes.

## When to choose it

Choose Void when you want an XBPS/runit image with a compact rolling base.

## Supported branches / releases

| Branch / release |
| --- |
| `current` |
| `glibc` |

Defaults:

- Branch/release: `current`
- Architecture: `x86_64`; choices: `x86_64`
- User: `void`
- Hostname: `ledit-void`
- Output image: `ledit-void.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/backend/scripts/build-void-usb.sh` |
| Configure backend | `ledit_core/backend/scripts/configure-void-usb.sh` |
| Branch variable | `VOID_REPOSITORY` |
| Main prefix | `VOID_USB` |
| Shared prefix | `LEDIT_USB` |

The backend uses `xbps-install -r` style installroot behavior and then configures the mounted target system.

## Host requirements

- **macOS**: Docker Desktop using `ghcr.io/void-linux/void-glibc-full:latest`.
- **Linux**: `xbps-install -r`, GRUB, `parted`, `dosfstools`, and `e2fsprogs`.
- **Windows**: builds are not implemented; flash an already generated image with an external tool.

## Commands

```sh
./ledit distros
./ledit search firefox --distro void --branch current --limit 5
./ledit build --distro void --branch current --dry-run --ask-password -y
./ledit build --distro void --branch current --ask-password -y

./ledit build --distro void \
  --branch current \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-void.img" \
  --ask-password \
  --extra-packages "vim tmux curl" \
  -y
```

## GUI and TUI

In the GUI, select **Void Linux (glibc)**. Package suggestions use XBPS metadata.

In the TUI, run:

```sh
./ledit tui
```

Then select `void`.

## Profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want broad desktop and hardware defaults. |
| `minimal` | You want a smaller runit/XBPS base. |

## Bootloader support

GRUB and systemd-boot are supported by the profile layer. extlinux is not supported.

## Environment reference

| Variable family | Meaning |
| --- | --- |
| `VOID_REPOSITORY` | `current`, `glibc`, or explicit repository selector when accepted. |
| `VOID_USB_*` | Void-specific profile values. |
| `LEDIT_USB_*` | Shared profile values also passed for compatibility. |
| `VOID_USB_EXTRA_PACKAGES` | Extra XBPS package list. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION` | Graphical session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Service choices. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware choices. |

```txt
VOID_REPOSITORY=current
VOID_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package not found | Check the XBPS package name with `./ledit search`. |
| Build fails in Docker | Confirm Docker is running and can pull the Void glibc image. |
| Configure step fails | Check chroot/installroot permissions and mounted target paths. |
| Bootloader validation fails | Try `--bootloader grub`. |

## Backend notes

- The builder uses an XBPS installroot.
- The configure script runs inside the mounted target via chroot.
- `VOID_USB_EXTRA_PACKAGES` and `LEDIT_USB_EXTRA_PACKAGES` are both accepted.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
