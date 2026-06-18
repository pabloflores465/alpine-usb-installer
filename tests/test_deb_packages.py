from __future__ import annotations

import json
import time

import pytest

from alpine_usb.deb_packages import index


def test_validate_release_accepts_supported_defaults() -> None:
    assert index.validate_release("stable") == "stable"
    assert index.validate_release("trixie") == "trixie"


def test_validate_release_rejects_shelly_values() -> None:
    with pytest.raises(ValueError, match="Debian release"):
        index.validate_release("stable;rm")


def test_parse_apt_cache_search_extracts_packages() -> None:
    parsed = index.parse_apt_cache_search("firefox-esr - Mozilla Firefox web browser\nnot a package line\n")

    assert parsed == [
        {"name": "firefox-esr", "description": "Mozilla Firefox web browser", "version": "", "repo": "debian"}
    ]


def test_search_debian_packages_scores_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        index,
        "_apt_cache_search",
        lambda query: [
            {"name": "foo-tools", "description": "Firefox helpers", "version": "", "repo": "debian"},
            {"name": "firefox-esr", "description": "Mozilla Firefox", "version": "", "repo": "debian"},
            {"name": "bar", "description": "unrelated", "version": "", "repo": "debian"},
        ],
    )

    assert [pkg["name"] for pkg in index.search_official_deb_packages("stable", "amd64", "firefox", 5)] == [
        "firefox-esr",
        "foo-tools",
    ]


def test_debian_cache_read_write_round_trip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPINE_USB_DEB_CACHE_DIR", str(tmp_path))
    path = index.deb_cache_path("stable", "amd64")
    packages = [{"name": "bash", "description": "shell", "version": "5", "repo": "debian"}]

    index._write_cache(path, "stable", "amd64", packages)
    payload = json.loads(path.read_text())

    assert payload["version"] == index.CACHE_VERSION
    cached = index._read_cache(path)
    assert cached is not None
    assert cached[0] == packages
    assert cached[1] <= time.time()
