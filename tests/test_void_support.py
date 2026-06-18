from __future__ import annotations

import argparse
import json
import time

from alpine_usb.distros import get_distro
from alpine_usb.interfaces import cli
from alpine_usb.void_packages import index as void_index


def test_void_provider_defaults_and_validation() -> None:
    distro = get_distro("void")

    assert distro.label == "Void Linux (glibc)"
    assert distro.validate_branch("current") == "current"
    assert distro.default_arch == "x86_64"


def test_cli_void_defaults_and_environment() -> None:
    ns = argparse.Namespace(
        distro="void",
        profile="compatibility",
        image_size="16G",
        branch="latest-stable",
        arch="x86_64",
        user="alpine",
        password="secret",
        root_password=None,
        hostname="alpine-usb",
        timezone="UTC",
        locale="en_US.UTF-8",
        language="",
        console_keymap="us",
        xkb_layout="us",
        xkb_variant="",
        xkb_model="pc105",
        desktop="xfce",
        wm=["i3"],
        tiling_wms="sway",
        default_session="auto",
        display_manager="auto",
        network="networkmanager",
        wifi=True,
        bluetooth=True,
        audio="pipewire",
        browser="firefox",
        firmware="full",
        legacy_x11_drivers=True,
        bootloader="grub",
        kernel="lts",
        boot_timeout=3,
        systemd_boot_console_mode="max",
        auto_resize=True,
        extra_package=["vim"],
        extra_packages="htop",
    )

    env = cli.env_from_build_args(ns)

    assert env["LINUX_USB_DISTRO"] == "void"
    assert env["VOID_REPOSITORY"] == "current"
    assert env["ALPINE_USB_USER"] == "void"
    assert env["ALPINE_USB_HOSTNAME"] == "void-usb"
    assert env["VOID_USB_EXTRA_PACKAGES"] == "vim htop"


def test_void_search_uses_cache_and_ranking(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPINE_USB_VOID_CACHE_DIR", str(tmp_path))
    cache = void_index.void_cache_path("current", "x86_64")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "version": void_index.CACHE_VERSION,
                "fetched_at": time.time(),
                "packages": [
                    {"name": "firefox", "version": "1_1", "description": "Mozilla browser", "repo": "void"},
                    {"name": "foo-firefox", "version": "1_1", "description": "wrapper", "repo": "void"},
                ],
            }
        )
    )

    results = void_index.search_official_void_packages("current", "x86_64", "firefox", limit=2)

    assert [item["name"] for item in results] == ["firefox", "foo-firefox"]


def test_parse_xbps_query_lines() -> None:
    parsed = void_index._parse_xbps_lines(
        "[-] NetworkManager-1.48_1 network daemon\n[*] firefox-127.0_1 browser", "void"
    )

    assert parsed[0] == {"name": "NetworkManager", "version": "1.48_1", "description": "network daemon", "repo": "void"}
    assert parsed[1]["name"] == "firefox"
