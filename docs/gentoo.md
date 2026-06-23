# Gentoo Linux USB backend

LEDIT includes a real Gentoo provider and installed-image builder while preserving the Alpine backend.

## Implemented

- `--distro gentoo` in the unified CLI build/search commands.
- Gentoo dry-run validation through `backend/scripts/configure-gentoo-usb.sh`:
  - stage3 channel: `stable` or `testing` (default `stable`)
  - desktop/session choices: XFCE, GNOME, Plasma, MATE, LXQt, none, and supported WMs
  - display manager, bootloader, kernel, firmware, localization, users/passwords, network, Wi-Fi, Bluetooth, audio, browser, extra packages, and auto-resize package planning
- Gentoo package atom validation and a provider-backed package search/cache foundation.
- Offline curated package mappings for all feature toggles. If `eix` or `pkgcore` is installed locally, package search can use local Portage metadata before falling back to the curated catalogue.
- GUI/TUI discovery: distribution selection, Gentoo branch/channel values, package search labels, and Gentoo build path wiring.
- Full installed image build from official Gentoo OpenRC stage3:
  - downloads latest `stage3-amd64-openrc` metadata and tarball
  - verifies SHA512 from Gentoo `*.DIGESTS`
  - extracts stage3 into a Docker/Linux chroot
  - configures Portage, locale, keyboard, user/root passwords, sudo/doas, OpenRC services, and first-boot root auto-resize
  - installs the selected Portage atom plan with `emerge`
  - creates a raw GPT USB image with FAT32 ESP + ext4 root
  - installs removable GRUB UEFI at `/EFI/BOOT/BOOTX64.EFI`
- USB flashing and image validation remain distro-neutral and unchanged.

## Docker/Linux build model

On macOS, `backend/scripts/build-gentoo-usb.sh` automatically re-enters itself in a privileged `linux/amd64` Docker container, matching the shared Linux builder pattern. The first run builds a cached `gentoo builder image` image from `backend/docker/Dockerfile.gentoo-builder`; later runs reuse it.

Useful knobs:

```sh
GENTOO_USB_SKIP_BUILDER_CACHE=1   # use fresh Alpine container and apk add tools
GENTOO_USB_REBUILD_BUILDER=1      # rebuild cached Gentoo builder image
GENTOO_USB_FORCE_DOCKER=1         # use Docker path on Linux too
GENTOO_KEEP_BUILD_DIR=1           # keep /var/tmp/gentoo-usb-build-* for debugging
```

Native Linux builds need root because the builder mounts `/proc`, `/sys`, `/dev`, and `/run` into the stage3 chroot. Run as root or set `GENTOO_USB_FORCE_DOCKER=1`.

## Stage3 base and binary/source tradeoff

Gentoo defaults to an `amd64` OpenRC stage3 plan. The package map prefers binary-friendly choices where Gentoo provides them, notably `sys-kernel/gentoo-kernel-bin`, but Gentoo remains a source-based distribution by default. A full image build may take substantially longer than Alpine and may require binhost availability, USE flags, licenses, and keywording choices that are host/site specific.

The installer writes Portage defaults suitable for a broad desktop USB image:

- `GRUB_PLATFORMS="efi-64"`
- broad `VIDEO_CARDS`/`INPUT_DEVICES`
- permissive `ACCEPT_LICENSE` default (`*`) so firmware/browser packages can install
- binary-package preference via `--getbinpkg --usepkg` unless `GENTOO_USE_BINPKGS=0`
- `testing` branch maps to `~amd64` keywords

Extra site policy can be passed with:

```sh
GENTOO_USE_BINPKGS=0
GENTOO_EMERGE_SYNC=0
GENTOO_EMERGE_OPTS="--keep-going=y"
GENTOO_MAKEOPTS="-j4"
GENTOO_ACCEPT_LICENSE="* -@EULA"
GENTOO_USE_FLAGS="X wayland elogind dbus policykit udev opengl vulkan alsa -systemd"
```

## Current limitations

- Full installed Gentoo images currently support `x86_64`/`amd64` and GRUB removable UEFI only. Choose `--bootloader grub`.
- Docker Desktop/macOS runs the `linux/amd64` builder through emulation on Apple Silicon, so large desktop builds can be slow.
- Portage can still require package-specific USE/keyword/license decisions for unusual extra atoms.
- The builder creates an installed raw USB image, not a live ISO.

Example dry-run:

```sh
./ledit build --distro gentoo --branch stable --dry-run --password gentoo \
  --desktop xfce --display-manager lightdm --browser firefox \
  --extra-package app-misc/ranger
```

Minimal full build example:

```sh
./ledit build --distro gentoo --branch stable --password gentoo \
  --desktop none --display-manager none --network none --no-wifi --no-bluetooth \
  --audio none --browser none --bootloader grub -y
```

Package search:

```sh
./ledit search --distro gentoo --branch stable firefox
```
