from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

BRANCHES = ("stable", "testing")
ARCHES = ("amd64", "x86_64")
ATOM_RE = re.compile(r"^([A-Za-z0-9+_.-]+/[A-Za-z0-9+_.-]+|[A-Za-z0-9][A-Za-z0-9+_.-]*)$")
CACHE_VERSION = 1
DEFAULT_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

# Curated catalogue for feature parity knobs. Portage category/package atoms are
# used by the Gentoo dry-run and as an offline search base; installations may
# still need USE flags or keywording on real hardware.
FEATURE_PACKAGES: dict[str, tuple[str, ...]] = {
    "base": (
        "sys-apps/baselayout",
        "sys-apps/openrc",
        "sys-apps/shadow",
        "app-admin/sysklogd",
        "app-admin/sudo",
        "app-admin/doas",
        "app-shells/bash",
        "app-editors/vim",
        "app-misc/tmux",
        "net-misc/curl",
        "net-misc/wget",
        "dev-vcs/git",
        "sys-fs/e2fsprogs",
        "sys-fs/dosfstools",
        "sys-apps/util-linux",
        "sys-block/parted",
    ),
    "kernel:lts": ("sys-kernel/gentoo-kernel-bin",),
    "kernel:stable": ("sys-kernel/gentoo-kernel-bin",),
    "firmware:full": ("sys-kernel/linux-firmware",),
    "bootloader:grub": ("sys-boot/grub", "sys-boot/efibootmgr"),
    "bootloader:systemd-boot": ("sys-apps/systemd", "sys-boot/efibootmgr"),
    "desktop:xfce": ("xfce-base/xfce4-meta", "x11-terms/xfce4-terminal"),
    "desktop:gnome": ("gnome-base/gnome",),
    "desktop:plasma": ("kde-plasma/plasma-meta", "kde-apps/konsole"),
    "desktop:mate": ("mate-base/mate",),
    "desktop:lxqt": ("lxqt-base/lxqt-meta",),
    "dm:lightdm": ("x11-misc/lightdm", "x11-misc/lightdm-gtk-greeter"),
    "dm:sddm": ("x11-misc/sddm",),
    "dm:gdm": ("gnome-base/gdm",),
    "dm:lxdm": ("lxde-base/lxdm",),
    "dm:greetd": ("gui-libs/greetd", "gui-apps/tuigreet"),
    "wm:i3": ("x11-wm/i3",),
    "wm:sway": ("gui-wm/sway",),
    "wm:hyprland": ("gui-wm/hyprland",),
    "wm:awesome": ("x11-wm/awesome",),
    "wm:bspwm": ("x11-wm/bspwm",),
    "wm:openbox": ("x11-wm/openbox",),
    "wm:labwc": ("gui-wm/labwc",),
    "browser:firefox": ("www-client/firefox-bin",),
    "browser:firefox-esr": ("www-client/firefox-bin",),
    "browser:chromium": ("www-client/chromium",),
    "audio:pipewire": ("media-video/pipewire", "media-video/wireplumber"),
    "audio:alsa": ("media-libs/alsa-lib", "media-sound/alsa-utils"),
    "network:networkmanager": ("net-misc/networkmanager",),
    "wifi": (
        "net-wireless/wpa_supplicant",
        "net-wireless/iw",
    ),
    "bluetooth": ("net-wireless/bluez",),
    "x11": ("x11-base/xorg-server", "x11-drivers/xf86-input-libinput", "media-libs/mesa"),
    "legacy_x11": ("x11-drivers/xf86-video-amdgpu", "x11-drivers/xf86-video-nouveau", "x11-drivers/xf86-video-vesa"),
    "auto_resize": (),
}

PACKAGE_DESCRIPTIONS: dict[str, str] = {
    "sys-kernel/gentoo-kernel-bin": "Prebuilt Gentoo distribution kernel",
    "sys-kernel/linux-firmware": "Firmware blobs for Linux drivers",
    "sys-boot/grub": "GRUB boot loader",
    "xfce-base/xfce4-meta": "XFCE desktop meta package",
    "gnome-base/gnome": "GNOME desktop environment",
    "kde-plasma/plasma-meta": "KDE Plasma desktop meta package",
    "mate-base/mate": "MATE desktop environment",
    "lxqt-base/lxqt-meta": "LXQt desktop environment",
    "www-client/firefox": "Firefox web browser built from source",
    "www-client/firefox-bin": "Firefox prebuilt browser binary",
    "www-client/chromium": "Chromium web browser",
    "net-misc/networkmanager": "NetworkManager daemon and tools",
    "media-video/pipewire": "PipeWire multimedia server",
}


def validate_branch(branch: str) -> str:
    if branch not in BRANCHES:
        raise ValueError("Gentoo branch must be stable or testing")
    return branch


def normalize_arch(arch: str) -> str:
    if arch == "x86_64":
        return "amd64"
    if arch not in ARCHES:
        raise ValueError("Gentoo stage3 support currently targets amd64/x86_64")
    return arch


def validate_package_atom(atom: str) -> str:
    if not ATOM_RE.match(atom):
        raise ValueError(f"Invalid Gentoo package atom: {atom!r}")
    return atom


def gentoo_cache_dir() -> Path:
    explicit = os.environ.get("ALPINE_USB_GENTOO_CACHE_DIR")
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "alpine-usb-installer" / "gentoo-packages"


def _catalogue() -> list[dict[str, str]]:
    atoms = sorted({atom for atoms in FEATURE_PACKAGES.values() for atom in atoms} | set(PACKAGE_DESCRIPTIONS))
    return [
        {
            "name": atom,
            "description": PACKAGE_DESCRIPTIONS.get(atom, "Gentoo Portage package"),
            "version": "",
            "repo": "gentoo",
        }
        for atom in atoms
    ]


def _local_search(query: str, limit: int) -> list[dict[str, str]]:
    exe = shutil.which("eix") or shutil.which("pkgcore")
    if not exe:
        return []
    if Path(exe).name == "eix":
        cmd = [exe, "--format", "<category>/<name>\t<description>\n", "--pure-packages", query]
    else:
        cmd = [exe, "pquery", "--format", "%{category}/%{package}\\t%{summary}", query]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    results: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        name, _, desc = line.partition("\t")
        if ATOM_RE.match(name):
            results.append({"name": name, "description": desc, "version": "", "repo": "local-portage"})
        if len(results) >= limit:
            break
    return results


def fetch_gentoo_packages() -> list[dict[str, str]]:
    path = gentoo_cache_dir() / "catalogue.json"
    ttl_raw = os.environ.get("ALPINE_USB_GENTOO_CACHE_TTL", str(DEFAULT_CACHE_TTL_SECONDS))
    try:
        ttl = int(ttl_raw)
    except ValueError:
        ttl = DEFAULT_CACHE_TTL_SECONDS
    try:
        payload = json.loads(path.read_text())
        if payload.get("version") == CACHE_VERSION and time.time() - float(payload.get("fetched_at", 0)) < ttl:
            packages = payload.get("packages")
            if isinstance(packages, list):
                return packages
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    packages = _catalogue()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": CACHE_VERSION, "fetched_at": time.time(), "packages": packages}))
    except OSError:
        pass
    return packages


def search_gentoo_packages(query: str, limit: int = 10) -> list[dict[str, str]]:
    query = query.strip().lower()
    if len(query) < 2:
        return []
    local = _local_search(query, limit)
    if local:
        return local[:limit]
    terms = [term for term in re.split(r"\s+", query) if term]
    results = []
    for package in fetch_gentoo_packages():
        name = package["name"].lower()
        desc = package.get("description", "").lower()
        haystack = f"{name} {desc}"
        if not all(term in haystack for term in terms):
            continue
        pn = name.rsplit("/", 1)[-1]
        if name == query or pn == query:
            score = 0
        elif pn.startswith(query) or name.startswith(query):
            score = 1
        elif all(term in name for term in terms):
            score = 2
        else:
            score = 3
        results.append((score, len(name), package["name"], package))
    results.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in results[:limit]]


def feature_package_atoms(config: dict[str, object]) -> list[str]:
    atoms: list[str] = []
    seen: set[str] = set()

    def add(key: str) -> None:
        for atom in FEATURE_PACKAGES.get(key, ()):
            if atom not in seen:
                validate_package_atom(atom)
                seen.add(atom)
                atoms.append(atom)

    add("base")
    add(f"kernel:{config.get('kernel', 'lts')}")
    add(f"bootloader:{config.get('bootloader', 'grub')}")
    if config.get("firmware", "full") == "full":
        add("firmware:full")
    desktop = str(config.get("desktop", "xfce"))
    if desktop != "none":
        add("x11")
        add(f"desktop:{desktop}")
    for wm in str(config.get("tiling_wms", "")).split():
        add("x11")
        add(f"wm:{wm}")
    dm = str(config.get("display_manager", "auto"))
    if dm != "none":
        add(f"dm:{dm}")
    for key in ("browser", "audio", "network"):
        value = str(config.get(key, "none"))
        if value != "none":
            add(f"{key}:{value}")
    if bool(config.get("wifi", True)):
        add("wifi")
    if bool(config.get("bluetooth", True)):
        add("bluetooth")
    if bool(config.get("legacy_x11_drivers", True)):
        add("legacy_x11")
    if bool(config.get("auto_resize", True)):
        add("auto_resize")
    for atom in str(config.get("extra_packages", "")).split():
        validate_package_atom(atom)
        if atom not in seen:
            seen.add(atom)
            atoms.append(atom)
    return atoms
