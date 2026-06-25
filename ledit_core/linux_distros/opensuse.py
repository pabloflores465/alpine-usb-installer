from __future__ import annotations

import contextlib
import gzip
import json
import os
import re
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from ledit_core.backend.mirrors import OPENSUSE_TUMBLEWEED_OSS_URL, opensuse_oss_repo_url

PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*$")
RELEASE_RE = re.compile(r"^(tumbleweed|leap-15\.6|leap-16\.0)$")
OPENSUSE_RELEASES = ("tumbleweed", "leap-15.6", "leap-16.0")
OPENSUSE_SEARCH_REPOS = ("oss",)
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
_PRIMARY_NS = {"m": "http://linux.duke.edu/metadata/common"}


def validate_opensuse_release(release: str) -> str:
    if not RELEASE_RE.match(release):
        raise ValueError("openSUSE release must be tumbleweed, leap-15.6, or leap-16.0")
    return release


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def repo_base_url(release: str) -> str:
    release = validate_opensuse_release(release)
    if release == "tumbleweed":
        return OPENSUSE_TUMBLEWEED_OSS_URL
    version = release.removeprefix("leap-")
    return opensuse_oss_repo_url(version)


def cache_dir() -> Path:
    explicit = os.environ.get("LEDIT_USB_OPENSUSE_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "ledit" / "opensuse"


def _cache_path(release: str, arch: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{release}-{arch}")
    return cache_dir() / f"{safe}.json"


def _cache_enabled() -> bool:
    return os.environ.get("LEDIT_USB_OPENSUSE_CACHE", "1").lower() not in {"0", "no", "false", "off"}


def _cache_ttl_seconds() -> int:
    raw = os.environ.get("LEDIT_USB_OPENSUSE_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
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
        if not isinstance(item, dict) or not item.get("name"):
            continue
        clean.append(
            {
                "name": str(item.get("name") or ""),
                "description": str(item.get("description") or ""),
                "version": str(item.get("version") or ""),
                "repo": str(item.get("repo") or "oss"),
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


def _primary_location_from_repomd(text: str) -> str:
    root = ET.fromstring(text)
    for data in root.findall("{http://linux.duke.edu/metadata/repo}data"):
        if data.attrib.get("type") == "primary":
            location = data.find("{http://linux.duke.edu/metadata/repo}location")
            href = location.attrib.get("href") if location is not None else None
            if href:
                return href
    raise ValueError("openSUSE repodata does not contain primary metadata")


def parse_primary_xml(text: str, repo: str = "oss") -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    root = ET.fromstring(text)
    for pkg in root.findall("m:package", _PRIMARY_NS):
        if pkg.attrib.get("type") != "rpm":
            continue
        name = pkg.findtext("m:name", default="", namespaces=_PRIMARY_NS)
        if not name:
            continue
        version_el = pkg.find("m:version", _PRIMARY_NS)
        version = ""
        if version_el is not None:
            version = version_el.attrib.get("ver", "")
            rel = version_el.attrib.get("rel")
            if rel:
                version = f"{version}-{rel}" if version else rel
        packages.append(
            {
                "name": name,
                "description": pkg.findtext("m:description", default="", namespaces=_PRIMARY_NS),
                "version": version,
                "repo": repo,
            }
        )
    return sorted(packages, key=lambda item: item["name"])


def _download_packages(release: str, arch: str) -> list[dict[str, str]]:
    # openSUSE repository metadata is architecture-filtered by package entries; keep arch for cache/API parity.
    del arch
    base = repo_base_url(release)
    with urllib.request.urlopen(f"{base}/repodata/repomd.xml", timeout=20) as response:
        primary_href = _primary_location_from_repomd(response.read().decode("utf-8", errors="replace"))
    with urllib.request.urlopen(f"{base}/{primary_href}", timeout=30) as response:
        data = response.read()
    text = gzip.decompress(data).decode("utf-8", errors="replace") if primary_href.endswith(".gz") else data.decode()
    return parse_primary_xml(text)


def fetch_official_opensuse_packages(release: str, arch: str) -> list[dict[str, str]]:
    release = validate_opensuse_release(release)
    path = _cache_path(release, arch)
    cached = _read_cache(path) if _cache_enabled() else None
    ttl = _cache_ttl_seconds()
    if cached and (ttl < 0 or (ttl > 0 and time.time() - cached[1] < ttl)):
        return cached[0]
    try:
        packages = _download_packages(release, arch)
    except Exception:
        if cached:
            return cached[0]
        raise
    if _cache_enabled():
        with contextlib.suppress(OSError):
            _write_cache(path, release, arch, packages)
    return packages


def search_official_opensuse_packages(release: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_official_opensuse_packages(release, arch):
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        if not all(term in f"{name} {desc}" for term in terms):
            continue
        score = 0 if name == query else 1 if name.startswith(query) else 2 if all(term in name for term in terms) else 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]


_DESKTOP_PACKAGES = {
    "xfce": ["patterns-xfce-xfce", "xfce4-session"],
    "gnome": ["patterns-gnome-gnome"],
    "plasma": ["patterns-kde-kde_plasma", "plasma6-session"],
    "mate": ["patterns-mate-mate"],
    "lxqt": ["patterns-lxqt-lxqt"],
    "none": [],
}
_WM_PACKAGES = {
    "i3": "i3",
    "sway": "sway",
    "hyprland": "hyprland",
    "awesome": "awesome",
    "bspwm": "bspwm",
    "openbox": "openbox",
    "labwc": "labwc",
}
_DM_PACKAGES = {"lightdm": "lightdm", "sddm": "sddm", "gdm": "gdm", "lxdm": "lxdm", "greetd": "greetd"}
_BROWSER_PACKAGES = {"firefox": "MozillaFirefox", "firefox-esr": "MozillaFirefox", "chromium": "chromium"}


def opensuse_package_plan(config: dict[str, object]) -> list[str]:
    packages = [
        "patterns-base-base",
        "kernel-default",
        "systemd",
        "udev",
        "grub2",
        "grub2-x86_64-efi",
        "shim",
        "NetworkManager",
        "sudo",
        "bash",
        "curl",
        "wget",
        "vim",
        "timezone",
        "ca-certificates",
        "e2fsprogs",
        "dosfstools",
        "growpart",
    ]
    desktop = str(config.get("desktop", "xfce"))
    packages.extend(_DESKTOP_PACKAGES.get(desktop, []))
    for wm in str(config.get("tiling_wms", "")).split():
        if wm in _WM_PACKAGES:
            packages.append(_WM_PACKAGES[wm])
    dm = str(config.get("display_manager", "auto"))
    if dm == "auto":
        dm = {"gnome": "gdm", "plasma": "sddm", "lxqt": "sddm", "xfce": "lightdm", "mate": "lightdm"}.get(
            desktop, "none"
        )
        if dm == "none" and str(config.get("tiling_wms", "")):
            dm = "greetd"
    if dm in _DM_PACKAGES:
        packages.append(_DM_PACKAGES[dm])
    if config.get("network", "networkmanager") == "networkmanager":
        packages.append("NetworkManager")
    if config.get("wifi", True):
        packages.extend(["wpa_supplicant", "iw", "wireless-regdb"])
    if config.get("bluetooth", True):
        packages.extend(["bluez", "blueman"])
    if config.get("audio", "pipewire") == "pipewire":
        packages.extend(["pipewire", "wireplumber", "pipewire-pulseaudio"])
    elif config.get("audio") == "alsa":
        packages.append("alsa")
    browser = str(config.get("browser", "firefox"))
    if browser in _BROWSER_PACKAGES:
        packages.append(_BROWSER_PACKAGES[browser])
    if config.get("firmware", "full") == "full":
        packages.append("kernel-firmware-all")
    if config.get("bootloader", "grub") == "systemd-boot":
        packages.append("systemd-boot")
    extra = str(config.get("extra_packages", ""))
    packages.extend(validate_package_name(pkg) for pkg in extra.split())
    seen: set[str] = set()
    return [pkg for pkg in packages if not (pkg in seen or seen.add(pkg))]
