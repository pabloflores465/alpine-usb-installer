# LEDIT — Linux External Drive Installer Tool

LEDIT builds configurable, preinstalled Linux images for USB drives and external disks. It gives you three interfaces over the same build system:

- **Qt GUI** for visual configuration and package search.
- **Full-screen TUI** for terminal-first workflows.
- **CLI** for repeatable builds, dry-runs, package search, device listing, and flashing.

The goal is not to make a live ISO. LEDIT creates installed Linux images that can be written to a drive and booted as a portable system.

> License: GPL-2.0-only. See [`LICENSE`](LICENSE).

## Documentation map

This README is the product entry point: what LEDIT does, how to install it, how to run it, and where to go next. The deeper pages are split by task and by distro so the root README stays readable.

| Need | Go here |
| --- | --- |
| First run | [Quick start](#quick-start) |
| GUI details | [GUI workflow](#gui-workflow) |
| CLI commands | [CLI reference](#cli-reference) |
| Build options | [Configuration reference](docs/configuration.md) |
| Errors and host checks | [Troubleshooting](docs/troubleshooting.md) |
| Distro-specific behavior | [Per-distro docs](docs/distros/README.md) |
| License | [`LICENSE`](LICENSE) |

The documentation follows a simple pattern: quick start first, how-to recipes next, reference tables after that, and explanations/troubleshooting at the end.

## What LEDIT can build

| Distro | CLI id | Branch / release choices | Package search backend | Build backend |
| --- | --- | --- | --- | --- |
| Alpine Linux | `alpine` | `latest-stable`, `edge`, `v3.22`, `v3.21` | APK `main`, `community` | [`docs/distros/alpine.md`](docs/distros/alpine.md) |
| Arch Linux | `arch` | `rolling`, `stable` alias | Arch package API (`core`, `extra`, `multilib`) | [`docs/distros/arch.md`](docs/distros/arch.md) |
| Debian | `debian` | `stable`, `testing`, `sid`, `trixie`, `bookworm`, `forky` | APT / Debian package metadata | [`docs/distros/debian.md`](docs/distros/debian.md) |
| Fedora | `fedora` | `stable`, `latest`, `rawhide`, `42`, `41` | DNF metadata | [`docs/distros/fedora.md`](docs/distros/fedora.md) |
| Gentoo | `gentoo` | `stable`, `testing` | Portage package atoms | [`docs/distros/gentoo.md`](docs/distros/gentoo.md) |
| NixOS | `nixos` | `nixos-24.11`, `nixos-25.05`, `nixos-unstable` | nixpkgs | [`docs/distros/nixos.md`](docs/distros/nixos.md) |
| openSUSE | `opensuse` | `tumbleweed`, `leap-16.0`, `leap-15.6` | Zypper metadata | [`docs/distros/opensuse.md`](docs/distros/opensuse.md) |
| RHEL family | `rhel`, `rocky`, `alma`, `centos`, `centos-stream` | `9`, `10` | DNF metadata (`baseos`, `appstream`) | [`docs/distros/rhel.md`](docs/distros/rhel.md) |
| Slackware | `slackware` | `stable`, `current`, `15.0` | `PACKAGES.TXT` | [`docs/distros/slackware.md`](docs/distros/slackware.md) |
| Ubuntu | `ubuntu` | `24.04`, `noble`, `22.04`, `jammy` | APT / Ubuntu package metadata | [`docs/distros/ubuntu.md`](docs/distros/ubuntu.md) |
| Void Linux (glibc) | `void` | `current`, `glibc` | XBPS metadata | [`docs/distros/void.md`](docs/distros/void.md) |

Run this any time to see the currently wired choices from the application itself:

```sh
./ledit distros
```

## Features

- Build installed Linux USB/external-drive images from distro-specific backends.
- Configure image size, output path, distro branch, architecture, user, hostname, password handling, timezone, locale, keyboard, desktop, display manager, window managers, browser, audio, network, Wi-Fi, Bluetooth, firmware, bootloader, kernel flavor, boot timeout, and auto-resize.
- Search distro-native package repositories before adding extra packages.
- Re-search selected packages when switching distro in GUI/TUI.
- Use `compatibility` or `minimal` build profiles.
- Validate profiles with `--dry-run` before writing an image.
- Flash generated images to removable drives with whole-disk safety checks.
- Use Docker on macOS for Linux image builders that need mount/chroot/loop tooling.
- Use a `.qtvenv` bootstrap for GUI dependencies so the GUI can start even when the active project virtualenv lacks PySide6.

## Requirements

### Python

- Python 3.9+ is supported by the GUI dependency pins in `requirements.txt`.
- Python 3.10+ is recommended when available.
- The GUI creates `.qtvenv` automatically and installs Qt dependencies there.

### Build host

| Host | Status | Notes |
| --- | --- | --- |
| macOS | Supported through Docker for most builders | Docker Desktop must be installed and running. |
| Native Linux | Supported | Install the distro-specific build tools documented in each distro page. |
| Windows | Build not implemented | Use Windows only to flash an already generated raw image with Rufus or balenaEtcher. |

### Flashing tools

| Host | Required tools |
| --- | --- |
| macOS | `diskutil`, `dd`, administrator password |
| Linux | `lsblk`, `dd`, `sudo` or `pkexec` |
| Windows | Not implemented in LEDIT; use an external flasher |

## Quick start

Clone the repo and enter it:

```sh
git clone https://github.com/pabloflores465/ledit.git
cd ledit
```

Open the GUI:

```sh
./ledit gui
```

Open the terminal UI:

```sh
./ledit tui
```

List supported distros:

```sh
./ledit distros
```

Run a safe dry-run before building:

```sh
./ledit build --distro alpine --dry-run --ask-password -y
```

Build an image:

```sh
./ledit build --distro alpine --ask-password -y
```

The default output directory is:

```txt
/tmp/ledit/
```

## Recommended workflow

1. Run `./ledit doctor`.
2. Pick a distro with `./ledit distros`.
3. Search for packages with `./ledit search <name> --distro <id>`.
4. Run a dry-run with the same options you plan to build.
5. Build the image.
6. List removable drives with `./ledit devices`.
7. Flash only after confirming the target device is correct.

Example:

```sh
./ledit doctor
./ledit search firefox --distro ubuntu --branch 24.04
./ledit build --distro ubuntu --branch 24.04 --dry-run --ask-password -y
./ledit build --distro ubuntu --branch 24.04 --ask-password -y
./ledit devices
./ledit flash /tmp/ledit/ledit-ubuntu.img /dev/diskX
```

## GUI workflow

Start the GUI:

```sh
./ledit gui
```

What happens on first run:

1. `./ledit gui` checks whether it is already running inside `.qtvenv`.
2. If not, it creates `.qtvenv`.
3. It installs `requirements.txt`.
4. It re-executes through `.qtvenv/bin/python`.
5. Only then does it import the Qt GUI modules.

This avoids `ModuleNotFoundError: No module named 'PySide6'` when your project virtualenv does not include Qt.

Typical GUI flow:

1. Select a distro.
2. Choose the branch/release.
3. Choose image size and output path.
4. Configure user, hostname, timezone, locale, keyboard, and password behavior.
5. Choose desktop, display manager, browser, audio, networking, firmware, bootloader, and extra packages.
6. Use package search to validate package names.
7. Run the build.
8. Flash the generated image only after checking the device list.

## TUI workflow

Open the full-screen terminal interface:

```sh
./ledit tui
```

The TUI is useful when you want the same guided flow as the GUI but are working over SSH, inside a terminal emulator, or on a machine without a desktop environment.

Running `./ledit` without a subcommand opens the TUI by default.

## CLI reference

### `gui`

Open the Qt graphical interface:

```sh
./ledit gui
```

### `tui`

Open the full-screen terminal UI:

```sh
./ledit tui
```

### `build`

Build or validate a Linux image.

```sh
./ledit build --distro <id> [options]
```

Common examples:

```sh
# Dry-run only.
./ledit build --distro arch --dry-run --ask-password -y

# Minimal, no desktop.
./ledit build --distro debian --profile minimal --desktop none --browser none --ask-password -y

# Larger image with extra packages.
./ledit build --distro ubuntu \
  --branch 24.04 \
  --image-size 32G \
  --extra-package neovim \
  --extra-package "tmux htop" \
  --ask-password \
  -y

# Pin output path.
./ledit build --distro void \
  --output "$HOME/Downloads/ledit-void.img" \
  --ask-password \
  -y
```

Important build options:

| Option | Purpose |
| --- | --- |
| `--distro` | Select the distro backend. |
| `--branch`, `--release`, `--nixos-channel` | Select the distro branch/release/channel. |
| `--profile` | `compatibility` or `minimal`. |
| `--output`, `-o` | Final raw image path. |
| `--image-size`, `-s` | Minimum image size, for example `16G`. |
| `--arch` | Target architecture choice exposed by the selected distro. |
| `--hostname`, `--user` | Initial system identity. |
| `--ask-password` | Prompt for passwords without writing them to shell history. |
| `--password`, `--root-password` | Non-interactive password values; prefer `--ask-password` for manual runs. |
| `--desktop` | `xfce`, `gnome`, `plasma`, `mate`, `lxqt`, or `none`. |
| `--display-manager` | `auto`, `lightdm`, `sddm`, `gdm`, `lxdm`, `greetd`, or `none`. |
| `--default-session` | Desktop or WM session to start by default. |
| `--wm`, `--tiling-wms` | Add optional window managers. |
| `--browser` | `firefox-esr`, `firefox`, `chromium`, or `none`. |
| `--audio` | `pipewire`, `alsa`, or `none`. |
| `--network` | `networkmanager` or `none`. |
| `--wifi`, `--no-wifi` | Toggle Wi-Fi support packages/services. |
| `--bluetooth`, `--no-bluetooth` | Toggle Bluetooth packages/services. |
| `--bootloader` | `grub`, `systemd-boot`, or `extlinux` when supported by the distro. |
| `--kernel` | `lts`, `stable`, `generic`, or `huge`, depending on backend mapping. |
| `--firmware` | `full` or `none`. |
| `--legacy-x11-drivers`, `--no-legacy-x11-drivers` | Keep or skip broad Xorg video drivers. |
| `--auto-resize`, `--no-auto-resize` | Enable/disable first-boot root expansion where supported. |
| `--extra-package`, `--extra-packages` | Add distro-native packages. |
| `--dry-run` | Validate and print the generated plan without creating an image. |
| `--yes`, `-y` | Skip confirmation prompts. |

For a complete explanation of configuration behavior, see [`docs/configuration.md`](docs/configuration.md).

### `search`

Search official package repositories for a distro.

```sh
./ledit search firefox --distro alpine --limit 5
./ledit search sway --distro arch
./ledit search app-editors/vim --distro gentoo
./ledit search docker --distro void
```

### `distros`

Show supported distro ids and branch choices:

```sh
./ledit distros
```

### `devices`

List removable USB-like devices:

```sh
./ledit devices
```

### `flash`

Write an image to a whole removable drive.

```sh
./ledit flash /path/to/ledit.img /dev/diskX
```

Flashing permanently erases the target drive. LEDIT performs image validation and whole-disk safety checks, but you must still verify the selected device.

### `doctor`

Check whether common host tools are available:

```sh
./ledit doctor
```

## Configuration model

LEDIT normalizes GUI, TUI, and CLI choices into environment variables before calling a distro backend. The key pieces are:

- `IMAGE_SIZE`
- `OUTPUT_PATH`
- `LINUX_USB_DISTRO`
- `LEDIT_DISTRO`
- distro branch variable such as `ALPINE_BRANCH`, `ARCH_USB_BRANCH`, `UBUNTU_RELEASE`, or `NIXOS_CHANNEL`
- shared profile variables such as `*_USER`, `*_HOSTNAME`, `*_DESKTOP`, `*_BOOTLOADER`, and `*_EXTRA_PACKAGES`

The selected distro decides which prefix the backend uses. Some backends consume only `LEDIT_USB_*`; others receive both a distro prefix and the shared prefix.

Detailed reference: [`docs/configuration.md`](docs/configuration.md).

## Build profiles

| Profile | Purpose |
| --- | --- |
| `compatibility` | Default profile. Keeps broadly useful desktop, firmware, networking, audio, browser, and video compatibility choices enabled unless overridden. |
| `minimal` | Smaller image baseline. Use it when you want to explicitly add only what you need. |

Profiles are defaults, not locks. You can still override individual options:

```sh
./ledit build --distro fedora --profile minimal --desktop xfce --browser none --ask-password -y
```

## Extra packages

Extra packages can be repeated or space-separated:

```sh
./ledit build --distro arch --ask-password \
  --extra-package neovim \
  --extra-package "tmux htop" \
  --extra-package docker
```

LEDIT validates package names with the selected distro provider before sending them to the backend. When using the GUI/TUI, changing distro re-searches selected packages so you can catch package-name differences early.

## Flashing safety

Use the whole-disk device path, not a partition path.

Examples:

| Host | Whole disk example | Avoid |
| --- | --- | --- |
| macOS | `/dev/disk4` | `/dev/disk4s1` |
| Linux | `/dev/sdb` | `/dev/sdb1` |

Recommended sequence:

```sh
./ledit devices
./ledit flash /tmp/ledit/ledit.img /dev/diskX
```

On macOS, LEDIT writes through the raw disk path (`/dev/rdiskX`) after unmounting the disk. On Linux, it uses `dd` with `conv=fsync`.

## Troubleshooting

| Problem | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'PySide6'` | GUI dependencies are missing from the current venv or `.qtvenv` was created before dependency pins changed. | Pull latest, remove `.qtvenv`, then run `./ledit gui`. |
| Docker error on macOS | Docker Desktop is not running or cannot access the repo/output path. | Start Docker Desktop and retry from a normal terminal. |
| Package not found | Package name differs between distros or branch metadata. | Run `./ledit search <name> --distro <id> --branch <branch>`. |
| Unsupported bootloader | Not every backend supports every bootloader. | Use `--bootloader grub` unless a distro page says otherwise. |
| Dry-run fails | Invalid branch, package, desktop, bootloader, or architecture. | Check the selected distro page and rerun with `--dry-run`. |
| Flash command refuses target | The selected target is not a safe whole removable disk. | Run `./ledit devices` and verify the exact device path. |

More help: [`docs/troubleshooting.md`](docs/troubleshooting.md).

## Distro docs

Each distro has its own page with:

- when to choose it,
- supported branch/release values,
- default user/hostname/image name,
- backend script paths,
- host requirements,
- quick commands,
- GUI/TUI notes,
- bootloader support,
- environment variable reference,
- distro-specific troubleshooting.

Start here: [`docs/distros/README.md`](docs/distros/README.md).

## Development notes

Run tests:

```sh
python -m pytest
```

Run linting if installed:

```sh
python -m ruff check .
```

The README intentionally avoids a long repository tree. For navigation, use the documentation map above and the source names themselves:

- frontends live under `ledit_core/frontends/`,
- distro providers live under `ledit_core/linux_distros/`,
- image build orchestration lives under `ledit_core/image_builds/`,
- shell build adapters live under `backend/scripts/`,
- distro docs live under `docs/distros/`.

## License

GPL-2.0-only. See [`LICENSE`](LICENSE).
