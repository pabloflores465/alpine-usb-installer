from __future__ import annotations

import re

from ledit_core.build_profiles.presets import VALID_WMS
from ledit_core.slackware_packages.index import validate_package_name


def bool_enabled(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "yes", "true", "on", "enabled"}


def split_extra_packages(text: str) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()
    for package in [part for part in re.split(r"\s+", text.strip()) if part]:
        validate_package_name(package)
        if package not in seen:
            seen.add(package)
            packages.append(package)
    return packages


def slackware_package_set(config: dict[str, str]) -> list[str]:
    packages: list[str] = []
    seen: set[str] = set()

    def add(*names: str) -> None:
        for name in names:
            if name and name not in seen:
                validate_package_name(name)
                seen.add(name)
                packages.append(name)

    desktop = config.get("desktop", "xfce")
    display_manager = config.get("display_manager", "auto")
    default_session = config.get("default_session", "auto")
    browser = config.get("browser", "firefox")
    audio = config.get("audio", "pipewire")
    firmware = config.get("firmware", "full")
    kernel = config.get("kernel", "huge")
    network = config.get("network", "networkmanager")
    wms = [wm for wm in re.split(r"[\s,]+", config.get("wms", "").strip()) if wm]

    add("aaa_base", "bash", "coreutils", "e2fsprogs", "elilo", "grub", "pkgtools", "shadow", "sudo", "util-linux")
    if kernel in {"lts", "stable", "generic"}:
        add("kernel-generic", "kernel-modules")
    else:
        add("kernel-huge", "kernel-modules")
    if firmware == "full":
        add("kernel-firmware")
    if bool_enabled(config.get("auto_resize", "1")):
        add("cloud-utils")
    if network == "networkmanager":
        add("NetworkManager")
    if bool_enabled(config.get("wifi", "1")):
        add("wpa_supplicant", "wireless-tools")
    if bool_enabled(config.get("bluetooth", "1")):
        add("bluez", "bluez-libs")
    if audio == "pipewire":
        add("pipewire", "wireplumber", "alsa-utils")
    elif audio == "alsa":
        add("alsa-utils")
    if desktop != "none" or wms or display_manager not in {"none", "auto"}:
        add("xorg-server", "xinit", "mesa", "dejavu-fonts-ttf", "noto-fonts-ttf")
    if desktop == "xfce":
        add("xfce4-panel", "xfce4-session", "xfce4-settings", "xfdesktop", "xfwm4")
    elif desktop == "plasma":
        add("plasma-desktop", "plasma-workspace", "konsole")
    elif desktop == "mate":
        add("mate-panel", "mate-session-manager", "marco")
    elif desktop == "lxqt":
        add("lxqt-panel", "lxqt-session", "openbox")
    elif desktop == "gnome":
        # Slackware does not ship GNOME in the official tree; keep dry-run explicit.
        add("gnome-session")
    for wm in wms:
        if wm not in VALID_WMS:
            raise ValueError(f"Unsupported window manager: {wm}")
        mapping = {
            "awesome": "awesome",
            "bspwm": "bspwm",
            "i3": "i3",
            "labwc": "labwc",
            "openbox": "openbox",
            "sway": "sway",
            "hyprland": "hyprland",
        }
        add(mapping[wm])
    if default_session in VALID_WMS and default_session not in wms:
        add(default_session)
    if display_manager == "lightdm":
        add("lightdm")
    elif display_manager == "sddm":
        add("sddm")
    elif display_manager == "gdm":
        add("gdm")
    elif display_manager == "lxdm":
        add("lxdm")
    elif display_manager == "greetd":
        add("greetd")
    if browser == "firefox" or browser == "firefox-esr":
        add("mozilla-firefox")
    elif browser == "chromium":
        add("chromium")
    add(*split_extra_packages(config.get("extra_packages", "")))
    return packages
