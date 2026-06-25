from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from ledit_core.backend.mirrors import ARCH_PACKAGE_SEARCH_URL

ARCH_SEARCH_REPOS = ("core", "extra", "multilib")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.@-]*$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_arch_branch(branch: str) -> str:
    if branch not in {"rolling", "stable"}:
        raise ValueError("Arch branch must be rolling (stable is accepted as an alias)")
    return "rolling"


def validate_arch_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def arch_cache_dir() -> Path:
    explicit = os.environ.get("LEDIT_USB_ARCH_CACHE_DIR") or os.environ.get("LINUX_USB_ARCH_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "arch-packages"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def arch_search_cache_path(query: str, arch: str) -> Path:
    return arch_cache_dir() / _safe_key(arch) / f"{_safe_key(query.lower())}.json"


def _cache_enabled() -> bool:
    return os.environ.get("LEDIT_USB_ARCH_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("LEDIT_USB_ARCH_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
    results = payload.get("packages")
    fetched_at = payload.get("fetched_at")
    if not isinstance(results, list) or not isinstance(fetched_at, (int, float)):
        return None
    clean: list[dict[str, str]] = []
    for item in results:
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
                "repo": str(item.get("repo") or ""),
            }
        )
    return clean, float(fetched_at)


def _write_cache(path: Path, query: str, arch: str, packages: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": CACHE_VERSION, "query": query, "arch": arch, "fetched_at": time.time(), "packages": packages}
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        os.replace(tmp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)


def _normalize_arch(arch: str) -> str:
    if arch != "x86_64":
        raise ValueError("Arch Linux backend currently supports x86_64 only")
    return arch


def _download_arch_search(query: str, arch: str, limit: int) -> list[dict[str, str]]:
    params = urllib.parse.urlencode({"q": query, "arch": arch})
    with urllib.request.urlopen(f"{ARCH_PACKAGE_SEARCH_URL}?{params}", timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    results = []
    for item in payload.get("results", []):
        if item.get("repo") not in ARCH_SEARCH_REPOS:
            continue
        results.append(
            {
                "name": str(item.get("pkgname") or ""),
                "description": str(item.get("pkgdesc") or ""),
                "version": str(item.get("pkgver") or ""),
                "repo": str(item.get("repo") or ""),
            }
        )
    return [item for item in results if item["name"]][:limit]


def search_official_arch_packages(query: str, arch: str = "x86_64", limit: int = 10) -> list[dict[str, str]]:
    arch = _normalize_arch(arch)
    query = query.strip().lower()
    if len(query) < 2:
        return []
    cache_path = arch_search_cache_path(query, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages[:limit]
    try:
        packages = _download_arch_search(query, arch, limit)
    except Exception:
        if cached:
            return cached[0][:limit]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, query, arch, packages)
    return packages[:limit]
