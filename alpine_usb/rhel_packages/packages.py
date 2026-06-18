from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

RHEL_ALIASES = {
    "rhel": "rocky",
    "rocky": "rocky",
    "rockylinux": "rocky",
    "alma": "alma",
    "almalinux": "alma",
    "centos-stream": "centos-stream",
    "centos": "centos-stream",
    "stream": "centos-stream",
}
RHEL_DEFAULT_RELEASE = "9"
RHEL_RELEASE_RE = re.compile(r"^(9|10|[0-9]+(?:-stream)?)$")
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:-]*$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60

RHEL_VALID_WMS = ("i3", "sway", "openbox")
RHEL_REPO_PACKAGES = {
    "base": [
        "@core",
        "NetworkManager",
        "acl",
        "bash-completion",
        "ca-certificates",
        "chrony",
        "cloud-utils-growpart",
        "curl",
        "dnf",
        "e2fsprogs",
        "efibootmgr",
        "firewalld",
        "grub2-efi-x64",
        "grub2-tools",
        "kernel",
        "kbd",
        "less",
        "lvm2",
        "nano",
        "openssh-server",
        "passwd",
        "polkit",
        "rsync",
        "shadow-utils",
        "sudo",
        "systemd",
        "systemd-udev",
        "tar",
        "util-linux",
        "vim-minimal",
        "xfsprogs",
    ],
    "graphical": [
        "@base-x",
        "mesa-dri-drivers",
        "xorg-x11-drv-libinput",
        "xorg-x11-server-Xorg",
        "xorg-x11-xauth",
        "xorg-x11-xinit",
    ],
    "firmware": ["linux-firmware"],
    "wifi": ["NetworkManager-wifi", "iw", "wpa_supplicant"],
    "bluetooth": ["bluez", "bluez-tools"],
    "pipewire": ["pipewire", "pipewire-alsa", "pipewire-pulseaudio", "wireplumber"],
    "alsa": ["alsa-utils"],
    "xfce": ["@xfce-desktop-environment", "lightdm", "lightdm-gtk"],
    "gnome": ["@gnome-desktop", "gdm"],
    "plasma": ["@kde-desktop", "sddm"],
    "mate": ["@mate-desktop-environment", "lightdm", "lightdm-gtk"],
    "lxqt": ["@lxqt-desktop-environment", "sddm"],
    "lightdm": ["lightdm", "lightdm-gtk"],
    "sddm": ["sddm"],
    "gdm": ["gdm"],
    "i3": ["i3", "i3status", "i3lock", "dmenu", "xterm"],
    "sway": ["sway", "swaybg", "swayidle", "swaylock", "foot", "waybar", "mako", "xorg-x11-server-Xwayland"],
    "openbox": ["openbox", "obconf", "xterm"],
    "firefox": ["firefox"],
    "firefox-esr": ["firefox"],
    "chromium": ["chromium"],
}


def normalize_rhel_distro(value: str) -> str:
    key = value.strip().lower()
    try:
        return RHEL_ALIASES[key]
    except KeyError as exc:
        aliases = ", ".join(sorted(RHEL_ALIASES))
        raise ValueError(f"Unsupported RHEL-family distro {value!r}; use one of: {aliases}") from exc


def validate_rhel_release(release: str) -> str:
    if not RHEL_RELEASE_RE.match(release):
        raise ValueError("RHEL-family release must be a major version such as 9 or 10")
    return release


def validate_package_name(package: str) -> str:
    if not PACKAGE_RE.match(package):
        raise ValueError(f"Invalid package name: {package!r}")
    return package


def _append_unique(packages: list[str], values: list[str]) -> None:
    for package in values:
        if package not in packages:
            packages.append(package)


def resolve_rhel_packages(
    *,
    desktop: str,
    display_manager: str,
    wms: list[str],
    network: str,
    wifi: bool,
    bluetooth: bool,
    audio: str,
    browser: str,
    firmware: str,
    auto_resize: bool,
    extra_packages: str,
) -> list[str]:
    packages: list[str] = []
    _append_unique(packages, RHEL_REPO_PACKAGES["base"])
    if not auto_resize and "cloud-utils-growpart" in packages:
        packages.remove("cloud-utils-growpart")
    if firmware == "full":
        _append_unique(packages, RHEL_REPO_PACKAGES["firmware"])
    if network == "networkmanager" and wifi:
        _append_unique(packages, RHEL_REPO_PACKAGES["wifi"])
    if bluetooth:
        _append_unique(packages, RHEL_REPO_PACKAGES["bluetooth"])
    if audio in {"pipewire", "alsa"}:
        _append_unique(packages, RHEL_REPO_PACKAGES[audio])
    graphical = desktop != "none" or bool(wms) or display_manager not in {"none", "auto"}
    if graphical:
        _append_unique(packages, RHEL_REPO_PACKAGES["graphical"])
    if desktop != "none":
        _append_unique(packages, RHEL_REPO_PACKAGES[desktop])
    if display_manager not in {"auto", "none"}:
        _append_unique(packages, RHEL_REPO_PACKAGES.get(display_manager, []))
    for wm in wms:
        if wm not in RHEL_VALID_WMS:
            raise ValueError(f"Window manager {wm!r} is not mapped for RHEL-family builds")
        _append_unique(packages, RHEL_REPO_PACKAGES[wm])
    if browser != "none":
        _append_unique(packages, RHEL_REPO_PACKAGES[browser])
    for package in extra_packages.split():
        validate_package_name(package)
        _append_unique(packages, [package])
    return packages


def rhel_cache_dir() -> Path:
    explicit = os.environ.get("ALPINE_USB_RHEL_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "alpine-usb-installer" / "rhel-packages"


def _cache_path(distro: str, release: str, query: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", query.strip().lower()) or "all"
    return rhel_cache_dir() / normalize_rhel_distro(distro) / validate_rhel_release(release) / f"{safe}.json"


def _read_cache(path: Path) -> list[dict[str, str]] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != CACHE_VERSION:
        return None
    fetched_at = payload.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return None
    ttl = int(os.environ.get("ALPINE_USB_RHEL_CACHE_TTL", DEFAULT_CACHE_TTL_SECONDS))
    if ttl >= 0 and time.time() - fetched_at >= ttl:
        return None
    packages = payload.get("packages")
    if not isinstance(packages, list):
        return None
    return [item for item in packages if isinstance(item, dict) and item.get("name")]


def _write_cache(path: Path, packages: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": CACHE_VERSION, "fetched_at": time.time(), "packages": packages}
    path.write_text(json.dumps(payload, separators=(",", ":")))


def search_rhel_packages(distro: str, release: str, query: str, limit: int = 10) -> list[dict[str, str]]:
    distro = normalize_rhel_distro(distro)
    release = validate_rhel_release(release)
    query = query.strip()
    if len(query) < 2:
        return []
    cache = _cache_path(distro, release, query)
    cached = _read_cache(cache)
    if cached is not None:
        return cached[:limit]
    tool = shutil.which("dnf5") or shutil.which("dnf") or shutil.which("repoquery")
    if tool is None:
        raise RuntimeError("dnf/dnf5/repoquery is required for live RHEL-family package search")
    cmd = [tool]
    if Path(tool).name in {"dnf", "dnf5"}:
        cmd.extend(["repoquery", f"--releasever={release}", "--qf", "%{name}\t%{version}\t%{summary}", f"*{query}*"])
    else:
        cmd.extend([f"--releasever={release}", "--qf", "%{name}\t%{version}\t%{summary}", f"*{query}*"])
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "repoquery failed")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in proc.stdout.splitlines():
        name, _, rest = line.partition("\t")
        version, _, desc = rest.partition("\t")
        if not name or name in seen:
            continue
        seen.add(name)
        results.append({"name": name, "version": version, "description": desc, "repo": distro})
        if len(results) >= limit:
            break
    with contextlib.suppress(OSError):
        _write_cache(cache, results)
    return results
