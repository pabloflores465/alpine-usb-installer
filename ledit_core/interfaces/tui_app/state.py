from __future__ import annotations

import tempfile
from pathlib import Path

from ledit_core.image_builds import VALID_WMS
from ledit_core.linux_distros import distro_choices, get_distro

DEFAULT_IMAGE_NAME = "ledit.img"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "ledit"

CHOICES = {
    "image_size": ["8G", "16G", "24G", "32G", "64G", "128G"],
    "distro": list(distro_choices(visible_only=True)),
    "branch": ["latest-stable", "edge", "v3.22", "v3.21"],
    "arch": ["x86_64"],
    "timezone": ["UTC", "America/Mexico_City", "America/Bogota", "America/Lima", "America/Santiago", "Europe/Madrid"],
    "locale": ["en_US.UTF-8", "es_ES.UTF-8", "es_MX.UTF-8"],
    "console_keymap": ["la-latin1", "es", "us", "br-abnt2", "fr", "de"],
    "xkb_layout": ["latam", "es", "us", "br", "fr", "de"],
    "desktop": ["xfce", "gnome", "plasma", "mate", "lxqt", "none"],
    "display_manager": ["auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none"],
    "default_session": [
        "auto",
        "xfce",
        "gnome",
        "plasma",
        "mate",
        "lxqt",
        "i3",
        "sway",
        "hyprland",
        "awesome",
        "bspwm",
        "openbox",
        "labwc",
        "shell",
    ],
    "browser": ["firefox-esr", "firefox", "chromium", "none"],
    "audio": ["pipewire", "alsa", "none"],
    "network": ["networkmanager", "none"],
    "bootloader": ["grub", "systemd-boot"],
    "kernel": ["lts", "stable"],
    "firmware": ["full", "none"],
    "systemd_boot_console_mode": ["max", "auto", "keep", "0", "1", "2", "3"],
}

WM_CHOICES = list(VALID_WMS)

DEFAULT_CONFIG = {
    "distro": "alpine",
    "output": str(DEFAULT_OUTPUT_DIR / get_distro("alpine").default_image_name),
    "image_size": "16G",
    "branch": "latest-stable",
    "arch": "x86_64",
    "hostname": "ledit-linux",
    "user": "alpine",
    "password": "",
    "root_password": "",
    "timezone": "UTC",
    "locale": "en_US.UTF-8",
    "language": "",
    "console_keymap": "us",
    "xkb_layout": "us",
    "xkb_variant": "",
    "xkb_model": "pc105",
    "desktop": "xfce",
    "display_manager": "auto",
    "default_session": "auto",
    "wms": [],
    "browser": "firefox",
    "audio": "pipewire",
    "network": "networkmanager",
    "wifi": True,
    "bluetooth": True,
    "bootloader": "grub",
    "kernel": "lts",
    "firmware": "full",
    "legacy_x11_drivers": True,
    "boot_timeout": "3",
    "systemd_boot_console_mode": "max",
    "auto_resize": True,
    "extra_packages": "",
    "device": "",
}
