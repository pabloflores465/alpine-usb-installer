from __future__ import annotations

import argparse
import json

import pytest

from alpine_usb.arch_packages.index import search_official_arch_packages, validate_arch_branch
from alpine_usb.build_profiles.arch import arch_packages_from_env
from alpine_usb.interfaces import cli


def base_env(**overrides: str) -> dict[str, str]:
    env = {
        "ALPINE_USB_DESKTOP": "xfce",
        "ALPINE_USB_TILING_WMS": "i3 sway",
        "ALPINE_USB_DISPLAY_MANAGER": "auto",
        "ALPINE_USB_NETWORK": "networkmanager",
        "ALPINE_USB_WIFI": "1",
        "ALPINE_USB_BLUETOOTH": "1",
        "ALPINE_USB_AUDIO": "pipewire",
        "ALPINE_USB_BROWSER": "firefox",
        "ALPINE_USB_FIRMWARE": "full",
        "ALPINE_USB_BOOTLOADER": "grub",
        "ALPINE_USB_KERNEL_FLAVOR": "lts",
        "ALPINE_USB_AUTO_RESIZE": "1",
        "ALPINE_USB_LEGACY_X11_DRIVERS": "0",
        "ALPINE_USB_EXTRA_PACKAGES": "neovim",
    }
    env.update(overrides)
    return env


def test_arch_branch_accepts_rolling_and_stable_alias() -> None:
    assert validate_arch_branch("rolling") == "rolling"
    assert validate_arch_branch("stable") == "rolling"
    with pytest.raises(ValueError):
        validate_arch_branch("v3.22")


def test_arch_package_mapping_covers_desktop_wms_and_services() -> None:
    packages = arch_packages_from_env(base_env())

    assert "base" in packages
    assert "linux-lts" in packages
    assert "xfce4" in packages
    assert "i3-wm" in packages
    assert "sway" in packages
    assert "lightdm" in packages
    assert "NetworkManager" not in packages
    assert "networkmanager" in packages
    assert "bluez" in packages
    assert "pipewire" in packages
    assert "firefox" in packages
    assert "neovim" in packages


def build_namespace(**overrides: object) -> argparse.Namespace:
    values = {
        "distro": "arch",
        "profile": "compatibility",
        "image_size": "16G",
        "branch": "latest-stable",
        "arch": "x86_64",
        "user": "arch",
        "password": "secret",
        "root_password": None,
        "hostname": "arch-usb",
        "timezone": "UTC",
        "locale": "en_US.UTF-8",
        "language": "",
        "console_keymap": "us",
        "xkb_layout": "us",
        "xkb_variant": "",
        "xkb_model": "pc105",
        "desktop": "xfce",
        "wm": [],
        "tiling_wms": "",
        "default_session": "auto",
        "display_manager": "auto",
        "network": "networkmanager",
        "wifi": True,
        "bluetooth": True,
        "audio": "pipewire",
        "browser": "firefox",
        "firmware": "full",
        "legacy_x11_drivers": True,
        "bootloader": "grub",
        "kernel": "lts",
        "boot_timeout": 3,
        "systemd_boot_console_mode": "max",
        "auto_resize": True,
        "extra_package": None,
        "extra_packages": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_cli_arch_dry_run_env_uses_arch_distro() -> None:
    ns = build_namespace(distro="arch", branch="latest-stable", user="arch", hostname="arch-usb")
    env = cli.env_from_build_args(ns)

    assert env["LINUX_USB_DISTRO"] == "arch"
    assert env["ALPINE_BRANCH"] == "rolling"
    assert env["ARCH_USB_BRANCH"] == "rolling"


def test_arch_search_uses_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("ALPINE_USB_ARCH_CACHE_DIR", str(cache))
    path = cache / "x86_64" / "firefox.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "query": "firefox",
                "arch": "x86_64",
                "fetched_at": 9999999999,
                "packages": [{"name": "firefox", "description": "browser", "version": "1", "repo": "extra"}],
            }
        )
    )

    assert search_official_arch_packages("firefox", "x86_64", 5)[0]["name"] == "firefox"
