from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from ledit_core.apk_packages.index import PACKAGE_RE, validate_package_name
from ledit_core.linux_distros.fedora import validate_release

CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_fedora_package_name(package: str) -> str:
    return validate_package_name(package)


def fedora_cache_dir() -> Path:
    explicit = os.environ.get("LEDIT_USB_FEDORA_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "fedora-packages"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def fedora_cache_path(release: str, arch: str) -> Path:
    return fedora_cache_dir() / _safe_key(release) / f"{_safe_key(arch)}.json"


def _cache_enabled() -> bool:
    return os.environ.get("LEDIT_USB_FEDORA_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("LEDIT_USB_FEDORA_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
        if not name or not PACKAGE_RE.match(name):
            continue
        clean.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
                "version": str(item.get("version") or ""),
                "repo": str(item.get("repo") or "fedora"),
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


def parse_repoquery_lines(text: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        name, version, repo, description = parts
        if PACKAGE_RE.match(name):
            packages.append({"name": name, "version": version, "repo": repo, "description": description})
    return packages


def _repoquery_command(release: str, arch: str) -> list[str]:
    tool = shutil.which("dnf") or shutil.which("dnf5") or shutil.which("repoquery")
    if tool is None:
        raise RuntimeError("Fedora package search needs dnf, dnf5, repoquery, or a warm Fedora package cache")
    release_args = [] if release == "stable" else [f"--releasever={release}"]
    if Path(tool).name == "repoquery":
        return [tool, *release_args, f"--arch={arch}", "--qf", "%{name}\\t%{evr}\\t%{repoid}\\t%{summary}", "*"]
    return [
        tool,
        "repoquery",
        *release_args,
        f"--arch={arch}",
        "--qf",
        "%{name}\\t%{evr}\\t%{repoid}\\t%{summary}",
        "*",
    ]


def _download_fedora_packages(release: str, arch: str) -> list[dict[str, str]]:
    proc = subprocess.run(_repoquery_command(release, arch), text=True, capture_output=True, timeout=90, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"repoquery failed with exit code {proc.returncode}")
    return sorted(parse_repoquery_lines(proc.stdout), key=lambda item: item["name"])


def fetch_fedora_packages(release: str, arch: str) -> list[dict[str, str]]:
    release = validate_release(release)
    cache_path = fedora_cache_path(release, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages
    try:
        packages = _download_fedora_packages(release, arch)
    except Exception:
        if cached:
            return cached[0]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, release, arch, packages)
    return packages


def search_fedora_packages(release: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_fedora_packages(release, arch):
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        haystack = f"{name} {desc}"
        if not all(term in haystack for term in terms):
            continue
        score = 0 if name == query else 1 if name.startswith(query) else 2 if all(term in name for term in terms) else 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]
