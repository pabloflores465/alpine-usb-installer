from __future__ import annotations

import contextlib
import io
import json
import os
import re
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from ledit_core.backend.mirrors import ALPINE_MIRROR

APK_MIRROR = ALPINE_MIRROR
APK_SEARCH_REPOS = ("main", "community")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
BRANCH_RE = re.compile(r"^(latest-stable|edge|v[0-9]+\.[0-9]+)$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def validate_branch(branch: str) -> str:
    if not BRANCH_RE.match(branch):
        raise ValueError("Alpine branch must be latest-stable, edge, or v<major>.<minor> (for example v3.22)")
    return branch


def official_repository_urls(branch: str) -> tuple[str, ...]:
    branch = validate_branch(branch)
    return tuple(f"{APK_MIRROR}/{branch}/{repo}" for repo in APK_SEARCH_REPOS)


def render_repositories_file(branch: str) -> str:
    return "\n".join(official_repository_urls(branch)) + "\n"


def write_repositories_file(path: str | Path, branch: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_repositories_file(branch), encoding="utf-8")
    return target


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def validate_extra_packages(text: str) -> str | None:
    for package in [part for part in re.split(r"\s+", text.strip()) if part]:
        if not PACKAGE_RE.match(package):
            return f"Invalid package name: {package}"
    return None


def parse_apkindex(text: str, repo: str) -> list[dict[str, str]]:
    packages = []
    current: dict[str, str] = {}
    for line in [*text.splitlines(), ""]:
        if not line:
            name = current.get("P")
            if name:
                packages.append(
                    {
                        "name": name,
                        "description": current.get("T", ""),
                        "version": current.get("V", ""),
                        "repo": repo,
                    }
                )
            current = {}
            continue
        if len(line) > 2 and line[1] == ":":
            current[line[0]] = line[2:]
    return packages


def apk_cache_dir() -> Path:
    explicit = os.environ.get("LEDIT_USB_APK_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "apkindex"


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def apk_cache_path(branch: str, arch: str) -> Path:
    return apk_cache_dir() / _safe_key(branch) / f"{_safe_key(arch)}.json"


def _cache_enabled() -> bool:
    return os.environ.get("LEDIT_USB_APK_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("LEDIT_USB_APK_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
                "repo": str(item.get("repo") or ""),
            }
        )
    return clean, float(fetched_at)


def _write_cache(path: Path, branch: str, arch: str, packages: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": CACHE_VERSION,
        "branch": branch,
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


def _download_apk_packages(branch: str, arch: str) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for repo in APK_SEARCH_REPOS:
        url = f"{APK_MIRROR}/{branch}/{repo}/{arch}/APKINDEX.tar.gz"
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = next((m for m in tar.getmembers() if m.name.endswith("APKINDEX")), None)
            if member is None:
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            text = fh.read().decode("utf-8", errors="replace")
        for package in parse_apkindex(text, repo):
            # Keep main over community if a name ever appears in both repos.
            merged.setdefault(package["name"], package)
    return sorted(merged.values(), key=lambda item: item["name"])


def fetch_official_apk_packages(branch: str, arch: str) -> list[dict[str, str]]:
    branch = validate_branch(branch)
    cache_path = apk_cache_path(branch, arch)
    cached = _read_cache(cache_path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached:
        packages, fetched_at = cached
        if ttl < 0 or (ttl > 0 and time.time() - fetched_at < ttl):
            return packages

    try:
        packages = _download_apk_packages(branch, arch)
    except Exception:
        if cached:
            # Prefer stale cache over failing interactive search while offline.
            return cached[0]
        raise

    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(cache_path, branch, arch, packages)
    return packages


def search_official_apk_packages(branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_apk_packages(branch, arch):
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
