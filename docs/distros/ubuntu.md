# Ubuntu

> Distro id: `ubuntu` · Package manager: APT · Package search: Ubuntu APT repositories.

## Purpose

Use the Ubuntu backend when you want a familiar APT-based image using supported Ubuntu LTS releases.

## Supported branches / releases

| Branch / release |
| --- |
| `24.04` |
| `noble` |
| `22.04` |
| `jammy` |

Defaults:

- Branch/release: `24.04`
- Architecture: `x86_64`; choices: `x86_64`, `amd64`
- User: `ubuntu`
- Hostname: `ledit-ubuntu`
- Output image: `ledit-ubuntu.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/backend/scripts/build-ubuntu-usb.sh` |
| Configure backend | `ledit_core/backend/scripts/configure-ubuntu-usb.sh` |
| Branch variable | `UBUNTU_RELEASE` |
| Main prefix | `UBUNTU_USB` |
| Shared prefix | `LEDIT_USB` |

The backend uses a debootstrap-style root filesystem workflow and then runs the configure script inside the target root.

## Host requirements

- **macOS**: Docker Desktop with an Ubuntu container path.
- **Linux**: `debootstrap`, GRUB tools, `parted`, `dosfstools`, `e2fsprogs`, and permission to run privileged filesystem operations.
- **Windows**: builds are not implemented; flash an already generated image with an external tool.

## Commands

```sh
./ledit distros
./ledit search firefox --distro ubuntu --branch 24.04 --limit 5
./ledit build --distro ubuntu --branch 24.04 --dry-run --ask-password -y
./ledit build --distro ubuntu --branch 24.04 --ask-password -y

./ledit build --distro ubuntu \
  --branch 24.04 \
  --image-size 24G \
  --output "$HOME/Downloads/ledit-ubuntu.img" \
  --ask-password \
  --extra-packages "vim htop curl" \
  -y
```

## GUI and TUI

In the GUI, select **Ubuntu**. The release selector exposes version numbers and codenames. Package suggestions use Ubuntu APT metadata.

In the TUI, run:

```sh
./ledit tui
```

Then select `ubuntu`.

## Profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want broad desktop and hardware defaults. |
| `minimal` | You want a smaller base and will add packages manually. |

## Bootloader support

GRUB is the validated path. systemd-boot may be accepted by profile mapping. extlinux is not supported.

## Environment reference

| Variable family | Meaning |
| --- | --- |
| `UBUNTU_RELEASE` | `24.04`, `noble`, `22.04`, or `jammy`. |
| `UBUNTU_USB_*` | Ubuntu-specific profile values. |
| `LEDIT_USB_*` | Shared profile values also passed for compatibility. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION` | Graphical session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Service choices. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware choices. |
| `*_EXTRA_PACKAGES` | Extra APT packages. |

```txt
UBUNTU_RELEASE=24.04
UBUNTU_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package not found | Check the selected Ubuntu release and exact package name. |
| Build fails during base creation | Check Docker/Linux network access and release value. |
| Image does not start | Try GRUB first and keep firmware enabled. |
| Desktop missing | Run dry-run and verify desktop/display-manager choices. |

## Backend notes

- `24.04` and `noble` target the default LTS path.
- `22.04` and `jammy` are available for older LTS compatibility.
- Package names should be checked with `./ledit search` before adding extras.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
