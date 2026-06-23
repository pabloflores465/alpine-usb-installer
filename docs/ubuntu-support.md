# Ubuntu support

Ubuntu support is provider-based and selected with `--distro ubuntu`. The default release is Ubuntu 24.04 LTS (Noble); `--release 22.04`/`jammy` is also accepted.

Implemented parity:

- CLI build/dry-run validation with the shared LEDIT profile, desktop/session, display manager, kernel, firmware, localization, users, network, Wi-Fi, Bluetooth, audio, browser, extra package, bootloader, and auto-resize knobs.
- GUI/TUI distribution selectors and Ubuntu package search path.
- Apt package search/cache foundation (`apt-cache search` when available, stale-cache fallback when offline).
- Ubuntu package mapping for XFCE, GNOME, Plasma, MATE, LXQt, optional WMs, NetworkManager, PipeWire/ALSA, Bluetooth, firmware, browsers, and bootloaders.
- USB flashing and raw-image validation remain distro-neutral.

Known gaps/risks:

- Full Ubuntu image builds require root/privileged loop-device access plus `debootstrap`/GRUB tooling. macOS uses a privileged Ubuntu Docker container path analogous to the Linux image-builder Docker flow.
- Ubuntu `systemd-boot` package selection is mapped, but the first implementation installs GRUB in the build script. Use `--bootloader grub` for validated full builds until systemd-boot installation is completed.
- Apt search currently depends on host `apt-cache` or an existing cache rather than downloading Ubuntu Packages indexes directly.
