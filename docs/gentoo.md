# Gentoo Linux USB backend

This branch adds a real Gentoo provider foundation while preserving the existing Alpine backend.

## Implemented

- `--distro gentoo` in the unified CLI build/search commands.
- Gentoo dry-run validation through `configure-gentoo-usb.sh`:
  - stage3 channel: `stable` or `testing` (default `stable`)
  - desktop/session choices: XFCE, GNOME, Plasma, MATE, LXQt, none, and supported WMs
  - display manager, bootloader, kernel, firmware, localization, users/passwords, network, Wi-Fi, Bluetooth, audio, browser, extra packages, and auto-resize package planning
- Gentoo package atom validation and a provider-backed package search/cache foundation.
- Offline curated package mappings for all feature toggles. If `eix` or `pkgcore` is installed locally, package search can use local Portage metadata before falling back to the curated catalogue.
- GUI/TUI discovery: distribution selection, Gentoo branch/channel values, package search labels, and Gentoo build path wiring.
- USB flashing and image validation remain distro-neutral and unchanged.
- Full image compile fallback: downloads the current official Gentoo minimal amd64 ISO, verifies SHA512 from Gentoo `*.DIGESTS`, and writes that bootable artifact to the requested output path.

## Stage3 base and binary/source tradeoff

Gentoo defaults to an `amd64` OpenRC stage3 plan. The package map prefers binary-friendly choices where Gentoo provides them, notably `sys-kernel/gentoo-kernel-bin`, but Gentoo remains a source-based distribution by default. A full image build may take substantially longer than Alpine and may require binhost policy, USE flags, licenses, and keywording choices that are host/site specific.

## Current gap

The full compile path now produces a verified official Gentoo minimal ISO artifact. A custom installed Gentoo rootfs image remains future work: stage3 download/extract, Portage binhost/source policy, chrooted `emerge`, bootloader install, and first-boot services still need a site-specific builder.

Example dry-run:

```sh
./alpine-usb build --distro gentoo --branch stable --dry-run --password gentoo \
  --desktop xfce --display-manager lightdm --browser firefox \
  --extra-package app-misc/ranger
```

Package search:

```sh
./alpine-usb search --distro gentoo --branch stable firefox
```
