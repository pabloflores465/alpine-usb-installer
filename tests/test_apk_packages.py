from __future__ import annotations

import json
import time

import pytest

from alpine_usb.apk_packages import index

APKINDEX_TEXT = """P:firefox
V:1.0-r0
T:Web browser

P:vim
V:9.0-r0
T:Text editor

"""


def test_parse_apkindex_extracts_package_fields() -> None:
    packages = index.parse_apkindex(APKINDEX_TEXT, "community")

    assert packages == [
        {"name": "firefox", "description": "Web browser", "version": "1.0-r0", "repo": "community"},
        {"name": "vim", "description": "Text editor", "version": "9.0-r0", "repo": "community"},
    ]


@pytest.mark.parametrize("branch", ["latest-stable", "edge", "v3.22"])
def test_validate_branch_accepts_supported_names(branch: str) -> None:
    assert index.validate_branch(branch) == branch


@pytest.mark.parametrize("branch", ["", "3.22", "latest", "v3", "v3.22.1", "../edge"])
def test_validate_branch_rejects_unsupported_names(branch: str) -> None:
    with pytest.raises(ValueError):
        index.validate_branch(branch)


@pytest.mark.parametrize("package", ["firefox", "libstdc++", "python3-dev", "a.b_c"])
def test_validate_package_name_accepts_apk_names(package: str) -> None:
    assert index.validate_package_name(package) == package


@pytest.mark.parametrize("package", ["", "-bad", "bad/name", "bad name", "$(bad)"])
def test_validate_package_name_rejects_unsafe_names(package: str) -> None:
    with pytest.raises(ValueError):
        index.validate_package_name(package)


def test_validate_extra_packages_reports_first_invalid_name() -> None:
    assert index.validate_extra_packages("firefox vim") is None
    assert index.validate_extra_packages("firefox bad/name") == "Invalid package name: bad/name"


def test_search_scores_exact_prefix_name_then_description(monkeypatch: pytest.MonkeyPatch) -> None:
    packages = [
        {"name": "x-firefox-helper", "description": "Firefox helper", "version": "1", "repo": "community"},
        {"name": "firefox", "description": "Browser", "version": "1", "repo": "main"},
        {"name": "firefox-esr", "description": "ESR browser", "version": "1", "repo": "main"},
    ]
    monkeypatch.setattr(index, "fetch_official_apk_packages", lambda branch, arch: packages)

    results = index.search_official_apk_packages("latest-stable", "x86_64", "firefox", limit=3)

    assert [item["name"] for item in results] == ["firefox", "firefox-esr", "x-firefox-helper"]


def test_fetch_uses_disk_cache_until_ttl_expires(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def download(branch: str, arch: str) -> list[dict[str, str]]:
        calls["count"] += 1
        return [{"name": "firefox", "description": "Browser", "version": "1", "repo": "main"}]

    monkeypatch.setenv("ALPINE_USB_APK_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(index, "_download_apk_packages", download)

    first = index.fetch_official_apk_packages("latest-stable", "x86_64")
    second = index.fetch_official_apk_packages("latest-stable", "x86_64")

    assert first == second
    assert calls["count"] == 1


def test_fetch_falls_back_to_stale_cache_when_download_fails(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_path = tmp_path / "latest-stable" / "x86_64.json"
    cache_path.parent.mkdir(parents=True)
    cached = [{"name": "vim", "description": "Editor", "version": "9", "repo": "main"}]
    cache_path.write_text(
        json.dumps({"version": index.CACHE_VERSION, "fetched_at": time.time() - 999999, "packages": cached})
    )

    monkeypatch.setenv("ALPINE_USB_APK_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(index, "_download_apk_packages", lambda branch, arch: (_ for _ in ()).throw(OSError("offline")))

    assert index.fetch_official_apk_packages("latest-stable", "x86_64") == cached
