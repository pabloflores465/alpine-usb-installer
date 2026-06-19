from __future__ import annotations

import json
import time

import pytest

from alpine_usb.fedora_packages import index as fedora_index
from alpine_usb.interfaces import cli
from alpine_usb.linux_distros import fedora
from tests.test_cli_interface import namespace


def test_fedora_plan_maps_desktop_services_and_packages() -> None:
    plan = fedora.plan_from_options(
        release="stable",
        arch="x86_64",
        desktop="plasma",
        display_manager="auto",
        default_session="auto",
        wms=["sway"],
        network="networkmanager",
        wifi=True,
        bluetooth=True,
        audio="pipewire",
        browser="chromium",
        firmware="full",
        kernel="stable",
        bootloader="grub",
        auto_resize=True,
        legacy_x11_drivers=False,
        extra_packages="neovim",
    )

    assert plan.display_manager == "sddm"
    assert plan.default_session == "plasma"
    assert "kde-desktop-environment" in plan.groups
    assert "sway" in plan.packages
    assert "chromium" in plan.packages
    assert "neovim" in plan.packages
    assert "grub2-efi-x64-modules" in plan.packages
    assert "xorg-x11-drv-vesa" not in plan.packages
    assert "NetworkManager.service" in plan.enabled_services
    assert plan.default_target == "graphical.target"


@pytest.mark.parametrize("release", ["stable", "rawhide", "41"])
def test_fedora_release_validation_accepts_supported_values(release: str) -> None:
    assert fedora.validate_release(release) == release


@pytest.mark.parametrize("release", ["latest", "latest-stable"])
def test_fedora_release_validation_normalizes_latest_aliases(release: str) -> None:
    assert fedora.validate_release(release) == "stable"


@pytest.mark.parametrize("release", ["v3.22", "../41", ""])
def test_fedora_release_validation_rejects_alpine_or_unsafe_values(release: str) -> None:
    with pytest.raises(ValueError):
        fedora.validate_release(release)


def test_cli_fedora_env_uses_fedora_keys_and_plan() -> None:
    env = cli.env_from_build_args(
        namespace(
            distro="fedora",
            branch="latest",
            user="fedora",
            hostname="fedora-usb",
            kernel="lts",
            browser="firefox-esr",
            extra_package=["vim"],
            extra_packages="htop",
        )
    )

    assert env["LINUX_USB_DISTRO"] == "fedora"
    assert env["FEDORA_RELEASE"] == "stable"
    assert env["FEDORA_USB_USER"] == "fedora"
    assert env["FEDORA_USB_EXTRA_PACKAGES"] == "vim htop"
    assert "kernel" in env["FEDORA_USB_PACKAGES"].split()
    assert "Fedora does not ship an official LTS kernel" in env["FEDORA_USB_WARNINGS"]


def test_parse_repoquery_lines_extracts_fedora_package_fields() -> None:
    text = "firefox\t120-1.fc41\tfedora\tWeb browser\ninvalid/name\t1\tfedora\tBad\n"

    assert fedora_index.parse_repoquery_lines(text) == [
        {"name": "firefox", "version": "120-1.fc41", "repo": "fedora", "description": "Web browser"}
    ]


def test_fedora_search_scores_cached_packages(monkeypatch: pytest.MonkeyPatch) -> None:
    packages = [
        {"name": "x-firefox-helper", "description": "Firefox helper", "version": "1", "repo": "fedora"},
        {"name": "firefox", "description": "Browser", "version": "1", "repo": "fedora"},
        {"name": "firefox-wayland", "description": "Wayland", "version": "1", "repo": "fedora"},
    ]
    monkeypatch.setattr(fedora_index, "fetch_fedora_packages", lambda release, arch: packages)

    results = fedora_index.search_fedora_packages("stable", "x86_64", "firefox", limit=3)

    assert [item["name"] for item in results] == ["firefox", "firefox-wayland", "x-firefox-helper"]


def test_fedora_fetch_uses_cache_and_stale_fallback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_path = tmp_path / "stable" / "x86_64.json"
    cache_path.parent.mkdir(parents=True)
    cached = [{"name": "vim", "description": "Editor", "version": "9", "repo": "fedora"}]
    cache_path.write_text(
        json.dumps({"version": fedora_index.CACHE_VERSION, "fetched_at": time.time() - 999999, "packages": cached})
    )

    monkeypatch.setenv("ALPINE_USB_FEDORA_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        fedora_index, "_download_fedora_packages", lambda release, arch: (_ for _ in ()).throw(OSError("offline"))
    )

    assert fedora_index.fetch_fedora_packages("stable", "x86_64") == cached
