from __future__ import annotations

import json
import time

import pytest

from alpine_usb.apt_packages import index


def test_validate_ubuntu_release_accepts_lts_aliases() -> None:
    assert index.validate_ubuntu_release("24.04") == "24.04"
    assert index.ubuntu_codename("noble") == "noble"
    assert index.ubuntu_codename("22.04") == "jammy"


def test_validate_ubuntu_release_rejects_unsupported() -> None:
    with pytest.raises(ValueError, match="Ubuntu release"):
        index.validate_ubuntu_release("mantic")


def test_parse_apt_cache_search_filters_package_names() -> None:
    parsed = index.parse_apt_cache_search(
        "firefox - Safe and easy web browser from Mozilla\nbad/name - invalid\nvim - Vi IMproved - enhanced vi editor\n"
    )

    assert parsed == [
        {
            "name": "firefox",
            "description": "Safe and easy web browser from Mozilla",
            "version": "",
            "repo": "apt-cache",
        },
        {"name": "vim", "description": "Vi IMproved - enhanced vi editor", "version": "", "repo": "apt-cache"},
    ]


def test_search_official_apt_packages_uses_fresh_cache(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPINE_USB_APT_CACHE_DIR", str(tmp_path))
    cache_path = index.apt_cache_path("24.04", "x86_64", "firefox")
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        json.dumps(
            {
                "version": index.CACHE_VERSION,
                "release": "24.04",
                "arch": "x86_64",
                "query": "firefox",
                "fetched_at": time.time(),
                "results": [
                    {"name": "firefox", "description": "browser", "version": "", "repo": "apt-cache"},
                ],
            }
        )
    )

    assert index.search_official_apt_packages("24.04", "x86_64", "firefox") == [
        {"name": "firefox", "description": "browser", "version": "", "repo": "apt-cache"}
    ]
