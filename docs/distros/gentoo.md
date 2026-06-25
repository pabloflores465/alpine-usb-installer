# Gentoo

> Distro id: `gentoo` · Package manager: Portage · Package search: Portage catalogue / local eix or pkgcore data.

## What this page covers

This page documents the `gentoo` backend: supported stage3 branch choices, backend scripts, Docker/native requirements, common commands, generated variables, and Gentoo-specific caveats.

## When to choose it

Choose Gentoo when you want a stage3-based image and are comfortable with longer build times.

## Supported branches / releases

| Branch / release |
| --- |
| `stable` |
| `testing` |

Defaults:

- Branch/release: `stable`
- Architecture: `x86_64`; choices: `x86_64`, `amd64`
- User: `gentoo`
- Hostname: `ledit-gentoo`
- Output image name: `ledit-gentoo.img`

## Backend implementation

| Role | Path |
| --- | --- |
| Build backend | `ledit_core/backend/scripts/build-gentoo-usb.sh` |
| Configure backend | `ledit_core/backend/scripts/configure-gentoo-usb.sh` |
| Branch environment variable | `GENTOO_STAGE3_BRANCH` |
| Distro environment prefix | `GENTOO_USB` |
| Shared profile prefix | `LEDIT_USB` |

LEDIT first normalizes options into environment variables. The Gentoo backend consumes those variables while preparing a stage3 root, package profile, boot files, and first-boot behavior.

## Host requirements

Docker Desktop on macOS using the Gentoo builder image from `ledit_core/backend/docker/Dockerfile.gentoo-builder`. Native Linux requires chroot-capable tooling, a stage3 tarball path, Portage, initramfs/kernel tooling, GRUB, and partition/filesystem tools.

## Quick commands

```sh
./ledit distros
./ledit search app-editors/vim --distro gentoo --branch stable --limit 5
./ledit build --distro gentoo --branch stable --dry-run --ask-password -y
./ledit build --distro gentoo --branch stable --ask-password -y

./ledit build --distro gentoo \
  --branch stable \
  --image-size 32G \
  --output "$HOME/Downloads/ledit-gentoo.img" \
  --ask-password \
  --extra-packages "app-editors/vim app-misc/tmux" \
  -y
```

## GUI and TUI notes

In the GUI, select **Gentoo**. Package search expects Gentoo-style package atoms where appropriate, for example `app-editors/vim`.

In the TUI, run `./ledit tui` and select `gentoo`.

## Build profiles

| Profile | Use it when |
| --- | --- |
| `compatibility` | You want a more complete desktop/hardware baseline. |
| `minimal` | You want to keep the image smaller and explicitly add packages. |

## Bootloader support

GRUB is supported. systemd-boot and extlinux are not exposed for this backend.

## Environment variable reference

The real prefix for this backend is `GENTOO_USB`. The backend also receives the shared `LEDIT_USB_*` variables.

| Variable family | Meaning |
| --- | --- |
| `GENTOO_STAGE3_BRANCH` | `stable` or `testing`. |
| `*_PROFILE` | `compatibility` or `minimal` build preset. |
| `*_USER`, `*_HOSTNAME` | Initial identity. |
| `*_PASSWORD_FILE`, `*_ROOT_PASSWORD_FILE` | Temporary secret files. |
| `*_DESKTOP`, `*_DISPLAY_MANAGER`, `*_DEFAULT_SESSION`, `*_TILING_WMS` | Desktop/session choices. |
| `*_NETWORK`, `*_WIFI`, `*_BLUETOOTH`, `*_AUDIO`, `*_BROWSER` | Services and desktop integration. |
| `*_BOOTLOADER`, `*_KERNEL_FLAVOR`, `*_FIRMWARE`, `*_AUTO_RESIZE` | Boot and hardware settings. |
| `*_EXTRA_PACKAGES` | Extra Portage atoms/package names. |

```txt
GENTOO_STAGE3_BRANCH=stable
GENTOO_USB_DRY_RUN=1
LEDIT_USB_DRY_RUN=1
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Package search returns nothing | Try the full category/package atom. |
| Build is slow | Gentoo builds are expected to take longer than binary-package distros. |
| Docker build fails | Rebuild or pull the Gentoo builder image and confirm Docker has enough disk space. |
| Bootloader validation fails | Use `--bootloader grub`. |

## Backend notes

- This is a stage3 bootstrap backend.
- The Docker builder image exists because Gentoo builds require a more controlled host environment.
- Expect longer build times than binary-package distributions.

## See also

- [Per-distro documentation index](README.md)
- [Project README](../../README.md)
- [General troubleshooting](../troubleshooting.md)
- [Configuration reference](../configuration.md)
