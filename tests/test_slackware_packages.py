from __future__ import annotations

import json
import time

import pytest

from alpine_usb.slackware_packages import index
from alpine_usb.slackware_packages.selection import slackware_package_set, split_extra_packages

PACKAGES_TXT = """
PACKAGE NAME:  mozilla-firefox-115.9.1esr-x86_64-1.txz
PACKAGE LOCATION:  ./xap
PACKAGE SIZE (compressed):  512 K
PACKAGE DESCRIPTION:
mozilla-firefox: Mozilla Firefox web browser
mozilla-firefox: Fast, private web browsing.

PACKAGE NAME:  NetworkManager-1.46.0-x86_64-2.txz
PACKAGE LOCATION:  ./n
PACKAGE DESCRIPTION:
NetworkManager: network connection manager
"""


def test_split_slackware_package_filename_keeps_hyphenated_name() -> None:
    assert index.split_slackware_package_filename("mozilla-firefox-115.9.1esr-x86_64-1.txz") == (
        "mozilla-firefox",
        "115.9.1esr-x86_64-1",
    )


def test_parse_packages_txt_extracts_names_descriptions_and_series() -> None:
    packages = index.parse_packages_txt(PACKAGES_TXT)

    assert packages[0]["name"] == "mozilla-firefox"
    assert packages[0]["repo"] == "xap"
    assert "web browser" in packages[0]["description"]
    assert packages[1]["name"] == "NetworkManager"
    assert packages[1]["repo"] == "n"


def test_release_path_defaults_stable_to_15() -> None:
    assert index.release_path("stable", "x86_64") == "slackware64-15.0"
    assert index.release_path("current", "x86_64") == "slackware64-current"


def test_search_uses_cache_and_ranks_exact_match(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPINE_USB_SLACKWARE_CACHE_DIR", str(tmp_path))
    cache_path = index.slackware_cache_path("stable", "x86_64")
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            {
                "version": index.CACHE_VERSION,
                "fetched_at": time.time(),
                "packages": index.parse_packages_txt(PACKAGES_TXT),
            }
        )
    )

    results = index.search_official_slackware_packages("stable", "x86_64", "firefox", limit=5)

    assert [pkg["name"] for pkg in results] == ["mozilla-firefox"]


def test_slackware_package_set_maps_common_desktop_options() -> None:
    packages = slackware_package_set(
        {
            "desktop": "xfce",
            "display_manager": "lightdm",
            "wms": "i3 sway",
            "browser": "firefox",
            "audio": "pipewire",
            "network": "networkmanager",
            "wifi": "1",
            "bluetooth": "0",
            "firmware": "full",
            "kernel": "generic",
            "auto_resize": "1",
            "extra_packages": "vim vim",
        }
    )

    assert "kernel-generic" in packages
    assert "xfce4-session" in packages
    assert "lightdm" in packages
    assert "i3" in packages
    assert "sway" in packages
    assert "mozilla-firefox" in packages
    assert packages.count("vim") == 1


def test_split_extra_packages_rejects_invalid_name() -> None:
    with pytest.raises(ValueError, match="Invalid package"):
        split_extra_packages("ok bad/name")
