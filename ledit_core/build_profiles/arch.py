from __future__ import annotations

import contextlib
import re

VALID_ARCH_WMS = ("i3", "sway", "hyprland", "awesome", "bspwm", "openbox", "labwc")

BASE_PACKAGES = (
    "base",
    "linux",
    "linux-firmware",
    "systemd",
    "sudo",
    "bash",
    "zsh",
    "curl",
    "wget",
    "git",
    "nano",
    "vim",
    "htop",
    "less",
    "e2fsprogs",
    "dosfstools",
    "util-linux",
    "noto-fonts",
    "noto-fonts-emoji",
)


def _enabled(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "yes", "true", "on", "enabled"}


def _append(packages: list[str], *names: str) -> None:
    for name in names:
        if name and name not in packages:
            packages.append(name)


def arch_packages_from_env(env: dict[str, str]) -> list[str]:
    desktop = env.get("LEDIT_USB_DESKTOP", "xfce").lower()
    wms = [part for part in re.split(r"[\s,]+", env.get("LEDIT_USB_TILING_WMS", "").strip()) if part]
    display_manager = env.get("LEDIT_USB_DISPLAY_MANAGER", "auto").lower()
    network = env.get("LEDIT_USB_NETWORK", "networkmanager").lower()
    audio = env.get("LEDIT_USB_AUDIO", "pipewire").lower()
    browser = env.get("LEDIT_USB_BROWSER", "firefox").lower()
    firmware = env.get("LEDIT_USB_FIRMWARE", "full").lower()
    bootloader = env.get("LEDIT_USB_BOOTLOADER", "grub").lower()
    kernel = env.get("LEDIT_USB_KERNEL_FLAVOR", "lts").lower()
    extra = [part for part in re.split(r"\s+", env.get("LEDIT_USB_EXTRA_PACKAGES", "").strip()) if part]
    packages = list(BASE_PACKAGES)

    if kernel == "lts":
        _append(packages, "linux-lts")
        packages.remove("linux")
    elif kernel == "stable":
        pass
    else:
        raise ValueError(f"Unsupported Arch kernel flavor: {kernel}")

    if firmware == "none":
        with contextlib.suppress(ValueError):
            packages.remove("linux-firmware")
    elif firmware != "full":
        raise ValueError(f"Unsupported Arch firmware option: {firmware}")

    if _enabled(env.get("LEDIT_USB_AUTO_RESIZE", "1")):
        _append(packages, "cloud-guest-utils")

    if bootloader == "grub":
        _append(packages, "grub", "efibootmgr")
    elif bootloader in {"systemd-boot", "systemdboot"}:
        _append(packages, "efibootmgr")
    else:
        raise ValueError(f"Unsupported Arch bootloader: {bootloader}")

    graphical = desktop != "none" or bool(wms) or display_manager not in {"auto", "none"}
    if graphical:
        _append(packages, "xorg-server", "xorg-xinit", "xorg-xrandr", "xorg-xsetroot", "mesa", "libinput", "xdg-utils")
        if _enabled(env.get("LEDIT_USB_LEGACY_X11_DRIVERS", "1")):
            _append(
                packages,
                "xf86-video-amdgpu",
                "xf86-video-ati",
                "xf86-video-intel",
                "xf86-video-nouveau",
                "xf86-video-vesa",
            )

    if desktop == "xfce":
        _append(packages, "xfce4", "xfce4-goodies", "xfce4-terminal", "gvfs", "udisks2")
    elif desktop == "gnome":
        _append(packages, "gnome", "gnome-terminal")
    elif desktop == "plasma":
        _append(packages, "plasma-meta", "konsole", "dolphin")
    elif desktop == "mate":
        _append(packages, "mate", "mate-extra", "mate-terminal", "gvfs", "udisks2")
    elif desktop == "lxqt":
        _append(packages, "lxqt", "qterminal", "pcmanfm-qt", "gvfs", "udisks2")
    elif desktop != "none":
        raise ValueError(f"Unsupported Arch desktop: {desktop}")

    for wm in wms:
        if wm not in VALID_ARCH_WMS:
            raise ValueError(f"Unsupported Arch window manager: {wm}")
        if wm == "i3":
            _append(packages, "i3-wm", "i3status", "i3lock", "dmenu", "xterm", "feh", "picom")
        elif wm == "sway":
            _append(
                packages,
                "sway",
                "swaybg",
                "swayidle",
                "swaylock",
                "foot",
                "waybar",
                "mako",
                "grim",
                "slurp",
                "xorg-xwayland",
            )
        elif wm == "hyprland":
            _append(packages, "hyprland", "foot", "waybar", "mako", "xorg-xwayland")
        else:
            _append(packages, wm)

    if display_manager == "auto":
        display_manager = {"gnome": "gdm", "plasma": "sddm", "lxqt": "sddm", "xfce": "lightdm", "mate": "lightdm"}.get(
            desktop, "greetd" if wms else "none"
        )
    if display_manager == "lightdm":
        _append(packages, "lightdm", "lightdm-gtk-greeter")
    elif display_manager in {"sddm", "gdm", "lxdm", "greetd"}:
        _append(packages, display_manager)
    elif display_manager != "none":
        raise ValueError(f"Unsupported Arch display manager: {display_manager}")

    if network == "networkmanager":
        _append(packages, "networkmanager")
        if _enabled(env.get("LEDIT_USB_WIFI", "1")):
            _append(packages, "iwd", "wireless_tools", "wpa_supplicant")
    elif network != "none":
        raise ValueError(f"Unsupported Arch network backend: {network}")

    if _enabled(env.get("LEDIT_USB_BLUETOOTH", "1")):
        _append(packages, "bluez", "bluez-utils")

    if audio == "pipewire":
        _append(packages, "pipewire", "pipewire-pulse", "wireplumber", "alsa-utils")
    elif audio == "alsa":
        _append(packages, "alsa-utils")
    elif audio != "none":
        raise ValueError(f"Unsupported Arch audio option: {audio}")

    if browser == "firefox-esr":
        _append(packages, "firefox")
    elif browser in {"firefox", "chromium"}:
        _append(packages, browser)
    elif browser != "none":
        raise ValueError(f"Unsupported Arch browser: {browser}")

    _append(packages, *extra)
    return packages
