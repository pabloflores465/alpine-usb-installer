# LEDIT per-distribution backends

LEDIT builds preinstalled Linux USB images using a distro-specific **backend** for each supported distribution. Every backend lives in [`backend/scripts/`](../../backend/scripts/) and is driven by the provider registry in [`ledit_core/linux_distros/providers.py`](../../ledit_core/linux_distros/providers.py).

This section documents each backend in a Distrobox-style page: supported branches, required host tools, environment variables consumed by the build/configure scripts, CLI/TUI/GUI usage, dry-run validation, and macOS/Linux/Windows notes.

Select a distro:

- [Alpine Linux](alpine.md)
- [Arch Linux](arch.md)
- [Debian](debian.md)
- [Fedora](fedora.md)
- [Gentoo](gentoo.md)
- [NixOS](nixos.md)
- [openSUSE](opensuse.md)
- [RHEL family](rhel.md)
- [Slackware](slackware.md)
- [Ubuntu](ubuntu.md)
- [Void Linux (glibc)](void.md)

> Doc style inspired by the [Distrobox documentation](https://github.com/89luca89/distrobox): one concise, actionable page per supported distro with commands, variables, and notes grouped by section.

## Common concepts

### Distro id

Every backend is selected by a stable `--distro` id (for example `alpine`, `arch`, `ubuntu`). Aliases like `rocky`/`alma`/`centos` resolve to a canonical id (`rhel`).

### Branch / release

Each backend exposes its own branch/release/channel choices (Alpine `latest-stable`/`edge`, Arch `rolling`, Debian `stable`/`testing`/`sid`, NixOS channels, etc.). The GUI and TUI refresh the list automatically when the distro changes.

### Package search

Package search is distro-native (APK, Pacman API, APT, DNF, Zypper, XBPS, nixpkgs, Portage, Slackware `PACKAGES.TXT`). When you switch distro with packages already selected, LEDIT re-searches those names in the new distro and reports any that are missing.

### Shared LEDIT environment

All backends read shared `LEDIT_USB_*` variables for the common profile (user, hostname, timezone, locale, keyboard, desktop, session, display manager, network, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, kernel, boot timeout, auto-resize, extra packages, profile). Distro-specific prefixes (`ALPINE_USB`, `ARCH_USB`, `DEBIAN_USB`, ...) are written alongside the shared prefix so each backend can read whichever it expects.

### Dry-run

Every backend supports `./ledit build --distro <id> --dry-run` without creating an image. Dry-run validates the generated configuration and package list on any host (including macOS).

### Build host requirements

- **Native Linux**: distro build tools (`debootstrap`, `pacstrap`, `dnf`, `zypper`, `xbps-install`, `nixos-generate`, GRUB/EFI tools, `parted`, filesystem tools, etc.).
- **macOS**: Docker Desktop for backends that need loop/mount/chroot support.
- **Windows**: not supported for builds; use the generated image with Rufus or balenaEtcher.

### Flashing

Flashing is distro-neutral and handled by `./ledit flash <image> <device>` with whole-disk safety checks and image validation.