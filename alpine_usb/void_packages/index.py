from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

VOID_REPOSITORIES = {
    "current": "https://repo-default.voidlinux.org/current",
    "glibc": "https://repo-default.voidlinux.org/current",
}
VOID_ARCHES = ("x86_64",)
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_void_repository(repository: str) -> str:
    if repository in VOID_REPOSITORIES or repository.startswith(("https://", "http://", "file://")):
        return repository
    raise ValueError("Void repository must be current, glibc, or an explicit repository URL")


def repository_url(repository: str) -> str:
    return VOID_REPOSITORIES.get(repository, repository).rstrip("/")


def validate_void_arch(arch: str) -> str:
    if arch not in VOID_ARCHES:
        raise ValueError("Void support currently targets glibc x86_64")
    return arch


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def void_cache_dir() -> Path:
    explicit = os.environ.get("ALPINE_USB_VOID_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "void-xbps"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def void_cache_path(repository: str, arch: str) -> Path:
    return void_cache_dir() / f"{_safe_key(repository)}-{_safe_key(arch)}.json"


def _cache_enabled() -> bool:
    return os.environ.get("ALPINE_USB_VOID_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("ALPINE_USB_VOID_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
    clean = []
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
                "repo": str(item.get("repo") or "void"),
            }
        )
    return clean, float(fetched_at)


def _write_cache(path: Path, repository: str, arch: str, packages: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "repository": repository,
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


def _parse_xbps_lines(text: str, repo: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # xbps-query -Rs: "[-] name-version description". Also accept cached/index-like "name version desc".
        line = re.sub(r"^\[[^]]+\]\s+", "", line)
        match = re.match(r"(?P<name>[A-Za-z0-9][A-Za-z0-9+_.-]*)-(?P<version>\S+)\s*(?P<desc>.*)", line)
        if not match:
            parts = line.split(maxsplit=2)
            if len(parts) < 2 or not PACKAGE_RE.match(parts[0]):
                continue
            packages.append(
                {
                    "name": parts[0],
                    "version": parts[1],
                    "description": parts[2] if len(parts) > 2 else "",
                    "repo": repo,
                }
            )
            continue
        packages.append(
            {
                "name": match.group("name"),
                "version": match.group("version"),
                "description": match.group("desc"),
                "repo": repo,
            }
        )
    return packages


def _query_with_xbps(repository: str, arch: str) -> list[dict[str, str]]:
    validate_void_arch(arch)
    cmd = ["xbps-query", "-R", "-r", "/", "--repository", repository_url(repository), "-s", ""]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
    return sorted(_parse_xbps_lines(proc.stdout, "void"), key=lambda item: item["name"])


def _query_index_url(repository: str, arch: str) -> list[dict[str, str]]:
    # Lightweight fallback for hosts without xbps-query. The x86_64-repodata file is zstd on modern Void;
    # if Python cannot decode it, callers still get stale cache when available.
    validate_void_arch(arch)
    url = f"{repository_url(repository)}/{arch}-repodata"
    with urllib.request.urlopen(url, timeout=20) as response:
        data = response.read().decode("utf-8", errors="replace")
    return sorted(_parse_xbps_lines(data, "void"), key=lambda item: item["name"])


def fetch_official_void_packages(repository: str, arch: str) -> list[dict[str, str]]:
    repository = validate_void_repository(repository)
    arch = validate_void_arch(arch)
    cache_path = void_cache_path(repository, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages
    try:
        try:
            packages = _query_with_xbps(repository, arch)
        except (FileNotFoundError, subprocess.SubprocessError):
            packages = _query_index_url(repository, arch)
    except Exception:
        if cached:
            return cached[0]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, repository, arch, packages)
    return packages


def search_official_void_packages(repository: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_void_packages(repository, arch):
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
