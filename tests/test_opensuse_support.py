from __future__ import annotations

import argparse

import pytest

from alpine_usb.interfaces import cli
from alpine_usb.linux_distros.opensuse import (
    opensuse_package_plan,
    parse_primary_xml,
    validate_opensuse_release,
)


def namespace(**overrides) -> argparse.Namespace:
    values = {
        "distro": "opensuse",
        "profile": "compatibility",
        "image_size": "16G",
        "branch": "latest-stable",
        "release": "tumbleweed",
        "arch": "x86_64",
        "user": "linux",
        "password": "secret",
        "root_password": None,
        "hostname": "opensuse-usb",
        "timezone": "UTC",
        "locale": "en_US.UTF-8",
        "language": "",
        "console_keymap": "us",
        "xkb_layout": "us",
        "xkb_variant": "",
        "xkb_model": "pc105",
        "desktop": "plasma",
        "wm": ["i3"],
        "tiling_wms": "sway",
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
        "kernel": "stable",
        "boot_timeout": 3,
        "systemd_boot_console_mode": "max",
        "auto_resize": True,
        "extra_package": ["vim"],
        "extra_packages": "git",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_opensuse_release_accepts_supported_values() -> None:
    assert validate_opensuse_release("tumbleweed") == "tumbleweed"
    assert validate_opensuse_release("leap-15.6") == "leap-15.6"
    with pytest.raises(ValueError, match="openSUSE release"):
        validate_opensuse_release("42.3")


def test_parse_primary_xml_extracts_rpm_packages() -> None:
    xml = """<?xml version="1.0"?><metadata xmlns="http://linux.duke.edu/metadata/common">
      <package type="rpm"><name>MozillaFirefox</name><version ver="1" rel="2"/><summary>Firefox</summary><description>Web browser</description></package>
    </metadata>"""
    assert parse_primary_xml(xml) == [
        {"name": "MozillaFirefox", "description": "Web browser", "version": "1-2", "repo": "oss"}
    ]


def test_opensuse_package_plan_maps_desktop_and_features() -> None:
    plan = opensuse_package_plan(
        {
            "desktop": "plasma",
            "tiling_wms": "i3 sway",
            "display_manager": "auto",
            "wifi": True,
            "bluetooth": False,
            "audio": "pipewire",
            "browser": "chromium",
            "firmware": "full",
            "extra_packages": "tmux",
        }
    )
    assert "patterns-kde-kde_plasma" in plan
    assert "sddm" in plan
    assert "wpa_supplicant" in plan
    assert "chromium" in plan
    assert "tmux" in plan


def test_cli_env_from_build_args_supports_opensuse() -> None:
    env = cli.env_from_build_args(namespace())
    assert env["OPENSUSE_RELEASE"] == "tumbleweed"
    assert env["OPENSUSE_USB_ROOT_PASSWORD"] == "secret"
    assert env["OPENSUSE_USB_TILING_WMS"] == "i3 sway"
    assert "patterns-kde-kde_plasma" in env["OPENSUSE_USB_PACKAGE_PLAN"]
    assert env["OPENSUSE_USB_EXTRA_PACKAGES"] == "vim git"
