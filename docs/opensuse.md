# openSUSE backend

The openSUSE backend is selectable with `--distro opensuse` in the CLI and appears in the TUI/GUI distro selectors. The default release is Tumbleweed; Leap 15.6 and 16.0 are accepted.

Implemented:

- dry-run validation through `configure-opensuse-usb.sh`
- package mapping for desktops, display managers, WMs, NetworkManager, Wi-Fi, Bluetooth, audio, browser, firmware, bootloader, auto-resize, and extras
- package search/cache from official openSUSE OSS repository metadata
- experimental Linux-only `build-opensuse-usb.sh` foundation using `zypper --root`

Known gap:

- the openSUSE image builder currently populates a root filesystem but bootable partition/fstab/initrd/grub finalization is experimental. Use dry-run and package search confidently; validate any produced openSUSE image manually before flashing.

Alpine build/flash behavior is unchanged.
