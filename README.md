# LEDIT — Linux External Drive Installer Tool

Build and flash configurable, preinstalled **Linux USB/external-drive images** from a Qt GUI, a full-screen TUI, or one unified CLI.

> License: GPL-2.0-only. See [`LICENSE`](LICENSE).

## Supported distributions

| Distro | CLI id | Branch / release choices shown by UI | Package search backend | Build backend |
| --- | --- | --- | --- | --- |
| Alpine Linux | `alpine` | `latest-stable`, `edge`, `v3.22`, `v3.21` | APK `main`, `community` | `backend/scripts/build-alpine-usb.sh` |
| Arch Linux | `arch` | `rolling`, `stable` alias | Arch package API (`core`, `extra`, `multilib`) | `backend/scripts/build-arch-usb.sh` |
| Debian | `debian` | `stable`, `testing`, `sid`, `trixie`, `bookworm`, `forky` | APT / `apt-cache` | `backend/scripts/build-debian-usb.sh` |
| Fedora | `fedora` | `stable`, `latest`, `rawhide`, numeric releases | DNF repoquery | `backend/scripts/build-fedora-usb.sh` |
| Gentoo | `gentoo` | `stable`, `testing` | Portage catalogue / local eix/pkgcore | `backend/scripts/build-gentoo-usb.sh` |
| NixOS | `nixos` | `nixos-24.11`, `nixos-25.05`, `nixos-unstable` | `nix search` / nixpkgs | Python NixOS image backend (`ledit_core/nixos`) |
| openSUSE | `opensuse` | `tumbleweed`, `leap-16.0`, `leap-15.6` | Zypper repo metadata | `backend/scripts/build-opensuse-usb.sh` |
| RHEL family | `rhel` | `9`, `10` | DNF repoquery | `backend/scripts/build-rhel-usb.sh` |
| Slackware | `slackware` | `stable`, `current`, `15.0` | Slackware `PACKAGES.TXT` | `backend/scripts/build-slackware-usb.sh` |
| Ubuntu | `ubuntu` | `24.04`, `noble`, `22.04`, `jammy` | APT / `apt-cache` | `backend/scripts/build-ubuntu-usb.sh` |
| Void Linux (glibc) | `void` | `current`, `glibc` | XBPS repositories | `backend/scripts/build-void-usb.sh` |

Detailed, Distrobox-style pages per distro are in [`docs/distros/`](docs/distros/README.md): branches, host tools, environment variables, CLI usage, and notes.

When you change distro in the GUI or TUI, the branch/release combo is replaced with only that distro's valid choices. Package suggestions also switch to that distro's repositories. If packages were already selected, LEDIT re-searches those names in the new distro and reports any missing package names.

## Features

- Build bootable installed Linux USB images from distro-specific builders.
- Configure image size, branch/release/channel, architecture, hostname, user/passwords, timezone, locale, keyboard, desktop/session, display manager, bootloader, kernel flavor, firmware, networking, Bluetooth, audio, browser, and extra packages.
- Search distro-native package repositories from GUI/TUI/CLI.
- Cache package indexes/search results for repeat searches.
- Use compatibility or minimal profiles.
- Flash generated raw images to USB from macOS/Linux with whole-disk safety checks and image validation.
- Auto-expand root filesystem on first boot where supported by distro backend.
- Validate code, scripts, distro dry-runs, and config matrix with project scripts.

## Requirements

### Build host

- Python 3.
- macOS: Docker Desktop for Linux image builders that need loop/mount/chroot support.
- Native Linux: distro backend tools as needed (`debootstrap`, `pacstrap`, `dnf`, `zypper`, `xbps-install`, `nix`/`nixos-generate`, GRUB/EFI tools, `parted`, filesystem tools, etc.).
- Alpine APK solver validation additionally needs Docker.

### Runtime flashing tools

- macOS flashing: `diskutil`, `dd`, administrator password.
- Linux flashing: `lsblk`, `dd`, `sudo` or `pkexec`.
- Windows raw flashing is not implemented; use Rufus or balenaEtcher with the generated image.

## Quick start

```sh
# GUI
./gui.py

# TUI by default
./ledit

# Explicit TUI
./ledit tui

# CLI help
./ledit --help
./ledit distros
./ledit build --help
```

Default output directory:

```txt
/tmp/ledit/
```

## CLI examples

```sh
# Search packages in selected distro repositories
./ledit search firefox --distro alpine
./ledit search firefox --distro ubuntu --branch 24.04
./ledit search sway --distro arch
./ledit search app-editors/vim --distro gentoo

# Validate without building
./ledit build --distro alpine --dry-run --ask-password --desktop xfce --bootloader systemd-boot
./ledit build --distro ubuntu --branch 24.04 --dry-run --ask-password --desktop plasma -y
./ledit build --distro nixos --branch nixos-25.05 --dry-run --password change-me -y

# Build minimal profiles
./ledit build --distro debian --profile minimal --ask-password -y
./ledit build --distro void --profile minimal --ask-password -y

# Build graphical image without broad legacy X11 drivers
./ledit build --distro fedora --ask-password --desktop xfce --no-legacy-x11-drivers -y

# List and flash devices
./ledit devices
./ledit flash /tmp/ledit/ledit.img /dev/sdX
```

Extra packages can be repeated or space-separated:

```sh
./ledit build --distro arch --ask-password \
  --extra-package neovim \
  --extra-package "tmux htop" \
  --extra-package docker
```

## GUI

```sh
./gui.py
```

The GUI creates and uses `.qtvenv` automatically if PySide6 is missing.

GUI flow:

1. Select distribution. Branch/release and package-search repositories update immediately.
2. Set image output path and system settings.
3. Open only the configuration sections you want to change.
4. Search/add extra packages from the selected distro repositories.
5. Build the image. The form stays editable for the next profile while a build runs.
6. Select USB target.
7. Flash USB. The image is checked before flashing.

GUI profiles can be saved/loaded as JSON/YAML. Password fields are never saved. Existing package selections are revalidated when you switch distros.

## TUI

```sh
./ledit
# or
./ledit tui
```

The TUI provides menus for distro selection, branch/release, package search, dry-run/build, USB selection, flashing, and host diagnostics.

## Build profiles

### Compatibility profile

Defaults are distro-like and graphical where possible:

| Option | Default |
| --- | --- |
| Image size | `16G` |
| Branch/release | distro default |
| Architecture | distro default (`x86_64`/equivalent) |
| Desktop | XFCE |
| Display manager | auto recommended |
| Bootloader | GRUB, except NixOS sd-image uses extlinux |
| Kernel | `lts` when backend supports it, else distro kernel |
| Firmware | full firmware |
| Network | NetworkManager + Wi‑Fi |
| Bluetooth | enabled |
| Audio | PipeWire |
| Browser | Firefox |
| USB auto-resize | enabled where supported |

### Minimal profile

`--profile minimal` changes defaults for smaller/faster images unless explicitly overridden:

| Option | Minimal default |
| --- | --- |
| Desktop | none |
| Display manager | none |
| Browser | none |
| Audio | none |
| Network | none |
| Wi‑Fi | disabled |
| Bluetooth | disabled |
| Firmware | none |
| Legacy X11 drivers | disabled |

## Distro notes

- **Alpine**: keeps the mature `alpine-make-vm-image` builder and APK `main/community` search.
- **Arch**: uses pacstrap-style package planning and Arch package API search.
- **Debian/Ubuntu**: use debootstrap-based builders and APT search.
- **Fedora/RHEL/openSUSE**: use DNF/Zypper installroot-style builders; package search may require local DNF/Zypper tooling or a warm cache.
- **Gentoo/Slackware/Void**: use distro-specific installroot/bootstrap flows; macOS paths run through Docker where implemented.
- **NixOS**: renders a flake/configuration and builds via `nixos-generate` or Docker.

Additional notes:

- Per-distro backends (Distrobox-style pages): [`docs/distros/`](docs/distros/README.md)
- [`docs/ubuntu-support.md`](docs/ubuntu-support.md)
- [`docs/gentoo.md`](docs/gentoo.md)
- [`docs/opensuse.md`](docs/opensuse.md)

## Repository layout

```
ledit                      # unified entrypoint (TUI default + CLI)
cli.py / gui.py / tui.py   # thin compatibility wrappers
apk_index.py              # thin wrapper over ledit_core.apk_packages
ledit_core/               # Python core package
├── frontends/            # CLI / GUI / TUI adapters (one folder each)
│   ├── cli/app.py
│   ├── gui/{app.py,workers.py}
│   └── tui/{app.py,state.py}
├── image_builds/         # build env, runtime workspace, secrets, dry-run, runners
├── package_search/       # distro-native package search service
├── linux_distros/        # provider registry + per-distro modules (fedora/gentoo/opensuse)
├── nixos/                # NixOS Python backend
├── {apk,apt,arch,deb,fedora,rhel,slackware,void}_packages/  # package index/search/cache per family
├── build_profiles/       # presets, config files, Arch profile
├── images/               # image validation
└── usb_devices/          # USB detection and safety
backend/
├── scripts/              # build-<distro>-usb.sh and configure-<distro>-usb.sh (all distros)
└── docker/               # Dockerfile.builder, Dockerfile.gentoo-builder
scripts/                  # project checks, builds, release assets, matrix
efi-fallback/             # standalone GRUB EFI + configs
docs/                     # README, per-distro pages, support notes
```

## Validation and tests

```sh
# Compile, lint, tests, shell syntax, smoke runs, distro dry-run checks
scripts/check-project.sh

# Distro dry-run compile smoke only
scripts/check-image-compile.sh

# Practical config matrix across all distros
scripts/validate-config-matrix.sh

# Exhaustive desktop/WM/DM/kernel grid
MATRIX_FULL=1 scripts/validate-config-matrix.sh

# Limit matrix to some distros while developing
MATRIX_DISTROS="alpine ubuntu nixos" scripts/validate-config-matrix.sh

# Include every known branch/release alias too
MATRIX_BRANCHES=all scripts/validate-config-matrix.sh

# Alpine dependency solver with real apk in Docker
scripts/check-apk-solver.sh
```

## Repository rebrand

GitHub repository name/description:

- Name: `ledit`
- Description: `Linux External Drive Installer Tool — build and flash configurable Linux USB images from GUI, TUI, or CLI.`

Local `origin` should point to `https://github.com/pabloflores465/ledit.git`.

## Troubleshooting

### Docker not running on macOS

Start Docker Desktop and retry. GUI-launched macOS apps get a small PATH; LEDIT adds common Docker/Homebrew/Nix paths automatically.

### Package search fails

Some backends use host tools (`apt-cache`, `dnf`, `zypper`, `nix`, `xbps-query`). Install the relevant tool or retry after a cache has been populated. Alpine, Arch, openSUSE, Slackware, and Void can use remote metadata or cache fallbacks depending on backend.

### Free build space on macOS

Large image builds can leave deleted-but-open temporary files if interrupted. Stop running Docker/build processes, run the GUI cleanup/stop path, or reboot if space is not released.

## License

GPL-2.0-only. See [`LICENSE`](LICENSE).
