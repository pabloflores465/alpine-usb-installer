from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from alpine_usb.apk_packages.index import PACKAGE_RE, validate_package_name

UBUNTU_RELEASE_ALIASES = {
    "24.04": "noble",
    "noble": "noble",
    "22.04": "jammy",
    "jammy": "jammy",
}
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
APT_SEARCH_REPOS = ("main", "universe", "restricted", "multiverse")


def validate_ubuntu_release(release: str) -> str:
    value = release.strip().lower()
    if value not in UBUNTU_RELEASE_ALIASES:
        raise ValueError("Ubuntu release must be 24.04/noble or 22.04/jammy")
    return value


def ubuntu_codename(release: str) -> str:
    return UBUNTU_RELEASE_ALIASES[validate_ubuntu_release(release)]


def apt_cache_dir() -> Path:
    explicit = os.environ.get("ALPINE_USB_APT_CACHE_DIR") or os.environ.get("LINUX_USB_APT_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "alpine-usb-installer" / "aptindex"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def apt_cache_path(release: str, arch: str, query: str) -> Path:
    return apt_cache_dir() / _safe_key(ubuntu_codename(release)) / _safe_key(arch) / f"{_safe_key(query.lower())}.json"


def _cache_enabled() -> bool:
    return os.environ.get("ALPINE_USB_APT_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("ALPINE_USB_APT_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS


def _read_cache(path: Path) -> tuple[list[dict[str, str]], float] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != CACHE_VERSION:
        return None
    results = payload.get("results")
    fetched_at = payload.get("fetched_at")
    if not isinstance(results, list) or not isinstance(fetched_at, (int, float)):
        return None
    clean = []
    for item in results:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name or not PACKAGE_RE.match(name):
            continue
        clean.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
                "version": str(item.get("version") or ""),
                "repo": str(item.get("repo") or "apt"),
            }
        )
    return clean, float(fetched_at)


def _write_cache(path: Path, release: str, arch: str, query: str, results: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": CACHE_VERSION,
                "release": release,
                "arch": arch,
                "query": query,
                "fetched_at": time.time(),
                "results": results,
            },
            separators=(",", ":"),
        )
    )


def parse_apt_cache_search(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for line in text.splitlines():
        if " - " not in line:
            continue
        name, desc = line.split(" - ", 1)
        name = name.strip()
        if not name or not PACKAGE_RE.match(name):
            continue
        results.append({"name": name, "description": desc.strip(), "version": "", "repo": "apt-cache"})
    return results


def _download_apt_search(_release: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    validate_package_name(query) if re.fullmatch(PACKAGE_RE, query) else None
    proc = subprocess.run(
        ["apt-cache", "search", "--names-only", query],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "apt-cache search failed")
    return parse_apt_cache_search(proc.stdout)[:limit]


def search_official_apt_packages(release: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    validate_ubuntu_release(release)
    query = query.strip().lower()
    if len(query) < 2:
        return []
    cache_path = apt_cache_path(release, arch, query)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages[:limit]
    try:
        results = _download_apt_search(release, arch, query, limit)
    except Exception:
        if cached:
            return cached[0][:limit]
        raise
    terms = [term for term in re.split(r"\s+", query) if term]
    scored = []
    for package in results:
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        if not all(term in f"{name} {desc}" for term in terms):
            continue
        score = 0 if name == query else 1 if name.startswith(query) else 2
        scored.append((score, len(name), package["name"], package))
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    clean_results = [item[3] for item in scored[:limit]]
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, release, arch, query, clean_results)
    return clean_results
