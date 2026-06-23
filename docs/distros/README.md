# Per-distro documentation

LEDIT supports multiple Linux distributions through distro-specific providers. Each provider defines:

- a stable CLI id,
- branch/release/channel choices,
- default architecture, user, hostname, and image name,
- package-search behavior,
- backend script or Python build path,
- environment prefix,
- bootloader constraints.

Use this index to choose the right backend before running a build.

## Supported distro pages

| Distro | CLI id / aliases | Package manager | Best use case |
| --- | --- | --- | --- |
| [Alpine Linux](alpine.md) | `alpine` | APK | Small OpenRC-based portable systems. |
| [Arch Linux](arch.md) | `arch` | Pacman | Rolling-release desktop or WM images. |
| [Debian](debian.md) | `debian` | APT | Conservative APT-based images. |
| [Fedora](fedora.md) | `fedora` | DNF | Modern DNF-based desktops and package groups. |
| [Gentoo](gentoo.md) | `gentoo` | Portage | Stage3-based images and Portage workflows. |
| [NixOS](nixos.md) | `nixos` | nixpkgs | Declarative image generation from Nix config. |
| [openSUSE](opensuse.md) | `opensuse`, `suse`, `opensuse-tumbleweed` | Zypper | Tumbleweed/Leap testing with Zypper metadata. |
| [RHEL family](rhel.md) | `rhel`, `rocky`, `rockylinux`, `alma`, `almalinux`, `centos`, `centos-stream` | DNF | Rocky/Alma/CentOS Stream compatible images. |
| [Slackware](slackware.md) | `slackware` | pkgtools | Classic Slackware package-series images. |
| [Ubuntu](ubuntu.md) | `ubuntu` | APT | Familiar LTS desktop/server-like USB images. |
| [Void Linux](void.md) | `void` | XBPS | Compact rolling glibc/runit images. |

## Common workflow for every distro

```sh
# 1. Confirm host tools.
./ledit doctor

# 2. List supported distros and branches.
./ledit distros

# 3. Search for packages using the selected distro backend.
./ledit search firefox --distro alpine --branch latest-stable

# 4. Validate the build profile without creating an image.
./ledit build --distro alpine --branch latest-stable --dry-run --ask-password -y

# 5. Build.
./ledit build --distro alpine --branch latest-stable --ask-password -y

# 6. Flash after confirming the target device.
./ledit devices
./ledit flash /tmp/ledit/ledit.img /dev/diskX
```

## Shared concepts

### Distro id

Every backend is selected by a stable `--distro` id. Some aliases resolve to a canonical provider. For example, `rocky`, `alma`, and `centos-stream` resolve to the RHEL-family backend.

### Branch / release / channel

The meaning of `--branch` depends on the distro:

| Distro | Meaning |
| --- | --- |
| Alpine | APK branch such as `latest-stable` or `edge`. |
| Arch | Rolling branch; `stable` is accepted as an alias. |
| Debian | Debian suite/codename such as `stable`, `testing`, `sid`, `trixie`, `bookworm`, or `forky`. |
| Fedora | Fedora release selector such as `stable`, `latest`, `rawhide`, `42`, or `41`. |
| Gentoo | Stage3 branch: `stable` or `testing`. |
| NixOS | NixOS channel such as `nixos-25.05`. |
| openSUSE | `tumbleweed` or Leap release. |
| RHEL family | Major release such as `9` or `10`. |
| Slackware | `stable`, `current`, or `15.0`. |
| Ubuntu | Ubuntu version/codename such as `24.04`, `noble`, `22.04`, or `jammy`. |
| Void | Repository selector such as `current` or `glibc`. |

### Package search

Package search is distro-native. That means names are not guaranteed to match across distributions. Search before adding extra packages:

```sh
./ledit search neovim --distro arch
./ledit search neovim --distro debian
./ledit search neovim --distro void
```

### Dry-run

Dry-run is the safest way to check a profile:

```sh
./ledit build --distro ubuntu --branch 24.04 --dry-run --ask-password -y
```

Dry-run catches invalid branches, unsupported bootloaders, invalid package names, missing package mappings, and generated package-plan warnings before image creation starts.

### macOS vs Linux

- On **macOS**, most full builds depend on Docker Desktop.
- On **Linux**, native builds need distro-specific installroot/chroot/bootloader tools.
- On **Windows**, LEDIT does not implement builds or native flashing. Use an already generated image with a separate flashing tool.

## Shared environment model

All frontends normalize settings into environment variables. The most important shared families are:

| Variable family | Purpose |
| --- | --- |
| `*_PROFILE` | `compatibility` or `minimal`. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Secret files generated before shell backends run. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION`, `*_TILING_WMS` | Graphical session profile. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Services and desktop integration. |
| `*_FIRMWARE`, `*_LEGACY_X11_DRIVERS`, `*_KERNEL_FLAVOR` | Hardware compatibility. |
| `*_BOOTLOADER`, `*_BOOT_TIMEOUT`, `*_SYSTEMD_BOOT_CONSOLE_MODE` | Boot configuration. |
| `*_AUTO_RESIZE` | First-boot expansion where supported. |
| `*_EXTRA_PACKAGES` | Distro-native extra package list. |

The selected distro page lists its exact prefix and branch variable.

## See also

- [Project README](../../README.md)
- [Configuration reference](../configuration.md)
- [Troubleshooting](../troubleshooting.md)
