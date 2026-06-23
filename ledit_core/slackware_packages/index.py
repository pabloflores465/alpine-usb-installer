from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path

SLACKWARE_MIRROR = "https://mirrors.slackware.com/slackware"
SLACKWARE_RELEASES = ("stable", "current", "15.0")
SLACKWARE_ARCHES = ("x86_64",)
SLACKWARE_SERIES = ("a", "ap", "d", "e", "f", "k", "kde", "l", "n", "t", "tcl", "x", "xap", "xfce", "y")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
RELEASE_RE = re.compile(r"^(stable|current|[0-9]+\.[0-9]+)$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_release(release: str) -> str:
    if not RELEASE_RE.match(release):
        raise ValueError("Slackware release must be stable, current, or <major>.<minor> (for example 15.0)")
    return release


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def release_path(release: str, arch: str) -> str:
    release = validate_release(release)
    if arch not in SLACKWARE_ARCHES:
        raise ValueError("Slackware support currently targets x86_64")
    if release == "stable":
        return "slackware64-15.0"
    if release == "current":
        return "slackware64-current"
    return f"slackware64-{release}"


def parse_packages_txt(text: str, series: str = "") -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    current: dict[str, str] = {}
    desc_lines: list[str] = []
    for raw_line in [*text.splitlines(), ""]:
        line = raw_line.rstrip("\n")
        if not line:
            if current.get("name"):
                description = " ".join(part.strip() for part in desc_lines if part.strip())
                packages.append(
                    {
                        "name": current["name"],
                        "description": description,
                        "version": current.get("version", ""),
                        "repo": series or current.get("series", ""),
                    }
                )
            current = {}
            desc_lines = []
            continue
        if line.startswith("PACKAGE NAME:"):
            file_name = line.split(":", 1)[1].strip()
            name, version = split_slackware_package_filename(file_name)
            current.update({"name": name, "version": version})
        elif line.startswith("PACKAGE LOCATION:"):
            location = line.split(":", 1)[1].strip()
            if not series:
                current["series"] = location.strip("./").split("/")[0]
        elif line.startswith("PACKAGE DESCRIPTION:"):
            continue
        elif current.get("name") and line.startswith(current["name"] + ":"):
            desc_lines.append(line.split(":", 1)[1])
    return packages


def split_slackware_package_filename(file_name: str) -> tuple[str, str]:
    base = file_name.rsplit("/", 1)[-1]
    for suffix in (".txz", ".tgz", ".tlz", ".tbz"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    parts = base.rsplit("-", 3)
    if len(parts) != 4:
        return base, ""
    name, version, arch, build = parts
    return name, f"{version}-{arch}-{build}"


def slackware_cache_dir() -> Path:
    explicit = os.environ.get("LEDIT_USB_SLACKWARE_CACHE_DIR") or os.environ.get("SLACKWARE_USB_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "slackware-packages"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def slackware_cache_path(release: str, arch: str) -> Path:
    return slackware_cache_dir() / _safe_key(release) / f"{_safe_key(arch)}.json"


def _cache_enabled() -> bool:
    return os.environ.get("LEDIT_USB_PACKAGE_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("LEDIT_USB_PACKAGE_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
        if isinstance(item, dict) and item.get("name"):
            clean.append(
                {
                    "name": str(item.get("name") or ""),
                    "description": str(item.get("description") or ""),
                    "version": str(item.get("version") or ""),
                    "repo": str(item.get("repo") or ""),
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


def _download_slackware_packages(release: str, arch: str) -> list[dict[str, str]]:
    path = release_path(release, arch)
    url = f"{SLACKWARE_MIRROR}/{path}/PACKAGES.TXT"
    with urllib.request.urlopen(url, timeout=20) as response:
        text = response.read().decode("utf-8", errors="replace")
    return sorted(parse_packages_txt(text), key=lambda item: item["name"])


def fetch_official_slackware_packages(release: str, arch: str) -> list[dict[str, str]]:
    release = validate_release(release)
    cache_path = slackware_cache_path(release, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages
    try:
        packages = _download_slackware_packages(release, arch)
    except Exception:
        if cached:
            return cached[0]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, release, arch, packages)
    return packages


def search_official_slackware_packages(release: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_slackware_packages(release, arch):
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
