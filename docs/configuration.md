# LEDIT configuration reference

This page explains the options shared by the GUI, TUI, and CLI. The CLI names are shown because they map directly to the environment variables sent to distro backends.

## Mental model

LEDIT has three layers:

1. **Frontend**: GUI, TUI, or CLI collects user choices.
2. **Profile normalization**: LEDIT resolves distro defaults, validates choices, converts secrets to temporary files, and creates environment variables.
3. **Distro backend**: a shell or Python backend builds and configures the target image.

The same configuration model is used no matter which frontend you use.

## Core build identity

| CLI option | Environment result | Meaning |
| --- | --- | --- |
| `--distro` | `LINUX_USB_DISTRO`, `LEDIT_DISTRO` | Selects the distro provider. |
| `--branch`, `--release`, `--nixos-channel` | Distro-specific branch variable | Selects release/channel/branch. |
| `--arch` | `ARCH` | Target architecture value accepted by the provider. |
| `--output`, `-o` | `OUTPUT_PATH` | Final raw image path. |
| `--image-size`, `-s` | `IMAGE_SIZE` | Minimum image size, for example `16G`. |

Branch variable examples:

| Distro | Branch variable |
| --- | --- |
| Alpine | `ALPINE_BRANCH` |
| Arch | `ARCH_USB_BRANCH` |
| Debian | `DEBIAN_RELEASE` |
| Fedora | `FEDORA_RELEASE` |
| Gentoo | `GENTOO_STAGE3_BRANCH` |
| NixOS | `NIXOS_CHANNEL` |
| openSUSE | `OPENSUSE_RELEASE` |
| RHEL family | `RHEL_USB_RELEASE` |
| Slackware | `SLACKWARE_RELEASE` |
| Ubuntu | `UBUNTU_RELEASE` |
| Void | `VOID_REPOSITORY` |

## Profiles

| Option | Values | Description |
| --- | --- | --- |
| `--profile` | `compatibility`, `minimal` | Selects the baseline preset. |

`compatibility` is the default. It favors a bootable graphical system on unknown hardware. `minimal` is a smaller baseline for users who want to explicitly add what they need.

Profiles set defaults; command-line options still override them.

## User and host settings

| CLI option | Variable family | Description |
| --- | --- | --- |
| `--user` | `*_USER` | Initial user account. |
| `--hostname` | `*_HOSTNAME` | Target hostname. |
| `--ask-password` | `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Prompts interactively and writes temporary secret files. |
| `--password` | converted to file before scripts run | Non-interactive password input; avoid for manual shell history. |
| `--root-password` | converted to file before scripts run | Root password; defaults to user password when omitted. |

Secrets are converted to files before shell backends run. Prefer `--ask-password` for manual usage.

## Locale and keyboard

| CLI option | Variable family | Default |
| --- | --- | --- |
| `--timezone` | `*_TIMEZONE` | `UTC` |
| `--locale` | `*_LOCALE` | `en_US.UTF-8` |
| `--language` | `*_LANGUAGE` | empty |
| `--console-keymap` | `*_CONSOLE_KEYMAP` | `us` |
| `--xkb-layout` | `*_XKB_LAYOUT` | `us` |
| `--xkb-variant` | `*_XKB_VARIANT` | empty |
| `--xkb-model` | `*_XKB_MODEL` | `pc105` |

## Desktop and session

| CLI option | Values |
| --- | --- |
| `--desktop` | `xfce`, `gnome`, `plasma`, `mate`, `lxqt`, `none` |
| `--display-manager` | `auto`, `lightdm`, `sddm`, `gdm`, `lxdm`, `greetd`, `none` |
| `--default-session` | `auto`, desktop names, supported WMs, `shell` |
| `--wm` | repeatable optional WM |
| `--tiling-wms` | comma/space-separated WM list |

The frontend collects these as one profile. The backend maps the profile into distro-native package names and services.

## Services and hardware compatibility

| CLI option | Values | Variable family |
| --- | --- | --- |
| `--browser` | `firefox-esr`, `firefox`, `chromium`, `none` | `*_BROWSER` |
| `--audio` | `pipewire`, `alsa`, `none` | `*_AUDIO` |
| `--network` | `networkmanager`, `none` | `*_NETWORK` |
| `--wifi` / `--no-wifi` | boolean | `*_WIFI` |
| `--bluetooth` / `--no-bluetooth` | boolean | `*_BLUETOOTH` |
| `--firmware` | `full`, `none` | `*_FIRMWARE` |
| `--legacy-x11-drivers` / `--no-legacy-x11-drivers` | boolean | `*_LEGACY_X11_DRIVERS` |

For unknown hardware, keep firmware and legacy X11 drivers enabled until the image has booted successfully at least once.

## Boot

| CLI option | Values | Variable family |
| --- | --- | --- |
| `--bootloader` | `grub`, `systemd-boot`, `extlinux` | `*_BOOTLOADER` |
| `--kernel` | `lts`, `stable`, `generic`, `huge` | `*_KERNEL_FLAVOR` |
| `--boot-timeout` | integer seconds | `*_BOOT_TIMEOUT` |
| `--systemd-boot-console-mode` | `max`, `auto`, `keep`, or numeric | `*_SYSTEMD_BOOT_CONSOLE_MODE` |
| `--auto-resize` / `--no-auto-resize` | boolean | `*_AUTO_RESIZE` |

Not every distro supports every bootloader. See the individual distro page before using `systemd-boot` or `extlinux`.

## Extra packages

You can add packages in two ways:

```sh
./ledit build --distro arch --extra-package neovim --extra-package tmux --ask-password
./ledit build --distro arch --extra-packages "neovim tmux htop" --ask-password
```

LEDIT validates package names before they are passed to the backend. Package existence depends on distro and branch.

## Dry-run

`--dry-run` validates the generated profile without creating an image:

```sh
./ledit build --distro debian --branch stable --dry-run --ask-password -y
```

Use dry-run when:

- trying a new distro,
- testing a package list,
- testing bootloader choices,
- checking generated package plans,
- running on macOS before a Docker-backed build.

## Environment prefixes

Every provider has a primary prefix. Some providers also receive `LEDIT_USB_*` variables for shared script compatibility.

| Distro | Primary prefix | Shared prefix |
| --- | --- | --- |
| Alpine | `LEDIT_USB` | `LEDIT_USB` |
| Arch | `ARCH_USB` | `LEDIT_USB` |
| Debian | `DEBIAN_USB` | `LEDIT_USB` |
| Fedora | `FEDORA_USB` | `LEDIT_USB` |
| Gentoo | `GENTOO_USB` | `LEDIT_USB` |
| NixOS | `NIXOS_USB` | `LEDIT_USB` |
| openSUSE | `OPENSUSE_USB` | `LEDIT_USB` |
| RHEL family | `RHEL_USB` | `LEDIT_USB` |
| Slackware | `SLACKWARE_USB` | `LEDIT_USB` |
| Ubuntu | `UBUNTU_USB` | `LEDIT_USB` |
| Void | `VOID_USB` | `LEDIT_USB` |

## Recommended presets

### Portable desktop

```sh
./ledit build --distro alpine \
  --profile compatibility \
  --desktop xfce \
  --display-manager auto \
  --browser firefox \
  --audio pipewire \
  --network networkmanager \
  --firmware full \
  --ask-password \
  -y
```

### Minimal server-like USB

```sh
./ledit build --distro debian \
  --profile minimal \
  --desktop none \
  --browser none \
  --audio none \
  --no-bluetooth \
  --ask-password \
  -y
```

### Tiling desktop

```sh
./ledit build --distro arch \
  --desktop none \
  --wm sway \
  --default-session sway \
  --browser firefox \
  --ask-password \
  -y
```

## See also

- [Project README](../README.md)
- [Per-distro documentation](distros/README.md)
- [Troubleshooting](troubleshooting.md)
