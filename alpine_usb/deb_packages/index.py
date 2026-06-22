from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

DEBIAN_DEFAULT_RELEASE = "stable"
DEBIAN_SEARCH_REPOS = ("apt-cache",)
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
RELEASE_RE = re.compile(r"^(stable|testing|sid|bookworm|trixie|forky)$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_release(release: str) -> str:
    if not RELEASE_RE.match(release):
        raise ValueError("Debian release must be stable, testing, sid, bookworm, trixie, or forky")
    return release


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def validate_extra_packages(text: str) -> str | None:
    for package in [part for part in re.split(r"\s+", text.strip()) if part]:
        if not PACKAGE_RE.match(package):
            return f"Invalid package name: {package}"
    return None


def deb_cache_dir() -> Path:
    explicit = os.environ.get("ALPINE_USB_DEB_CACHE_DIR") or os.environ.get("LINUX_USB_DEB_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "aptindex"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def deb_cache_path(release: str, arch: str) -> Path:
    return deb_cache_dir() / _safe_key(release) / f"{_safe_key(arch)}.json"


def _cache_enabled() -> bool:
    return os.environ.get("ALPINE_USB_DEB_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("ALPINE_USB_DEB_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
    packages = payload.get("packages")
    fetched_at = payload.get("fetched_at")
    if not isinstance(packages, list) or not isinstance(fetched_at, (int, float)):
        return None
    clean: list[dict[str, str]] = []
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        clean.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
                "version": str(item.get("version") or ""),
                "repo": str(item.get("repo") or "debian"),
            }
        )
    return clean, float(fetched_at)


def _write_cache(path: Path, release: str, arch: str, packages: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "release": release,
        "arch": arch,
        "fetched_at": time.time(),
        "packages": packages,
    }
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def parse_apt_cache_search(text: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for line in text.splitlines():
        if " - " not in line:
            continue
        name, description = line.split(" - ", 1)
        name = name.strip()
        if PACKAGE_RE.match(name):
            packages.append({"name": name, "description": description.strip(), "version": "", "repo": "debian"})
    return packages


def _apt_cache_search(query: str) -> list[dict[str, str]]:
    proc = subprocess.run(
        ["apt-cache", "search", "--names-only", query],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_apt_cache_search(proc.stdout)


def fetch_official_deb_packages(release: str, arch: str, query: str = "linux") -> list[dict[str, str]]:
    validate_release(release)
    cache_path = deb_cache_path(release, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages
    try:
        packages = _apt_cache_search(query)
    except Exception:
        if cached:
            return cached[0]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, release, arch, packages)
    return packages


def search_official_deb_packages(release: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    validate_release(release)
    terms = [term for term in re.split(r"\s+", query) if term]
    try:
        candidates = _apt_cache_search(query)
    except Exception:
        candidates = fetch_official_deb_packages(release, arch, query=query)
    results = []
    for package in candidates:
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        haystack = f"{name} {desc}"
        if not all(term in haystack for term in terms):
            continue
        if name == query:
            score = 0
        elif name.startswith(query):
            score = 1
        elif all(term in name for term in terms):
            score = 2
        else:
            score = 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]
