from __future__ import annotations

import re
from dataclasses import dataclass

from alpine_usb.apk_packages.index import validate_package_name
from alpine_usb.build_profiles.presets import VALID_WMS

FEDORA_DEFAULT_RELEASE = "stable"
FEDORA_RELEASE_RE = re.compile(r"^(stable|rawhide|[0-9]{2,3})$")
FEDORA_ARCHES = ("x86_64",)
FEDORA_DESKTOPS = ("xfce", "gnome", "plasma", "mate", "lxqt", "none")
FEDORA_DISPLAY_MANAGERS = ("auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none")
FEDORA_KERNELS = ("stable", "lts")
FEDORA_BOOTLOADERS = ("grub", "systemd-boot")
FEDORA_FIRMWARE = ("full", "none")


@dataclass(frozen=True)
class FedoraPlan:
    release: str
    arch: str
    packages: tuple[str, ...]
    groups: tuple[str, ...]
    enabled_services: tuple[str, ...]
    default_target: str
    display_manager: str
    default_session: str
    warnings: tuple[str, ...] = ()


def validate_release(release: str) -> str:
    if not FEDORA_RELEASE_RE.match(release):
        raise ValueError("Fedora release must be stable, rawhide, or a numeric release such as 41")
    return release


def resolve_release(release: str) -> str:
    """Return dnf --releasever value; stable lets dnf use the host/default Fedora repos."""
    release = validate_release(release)
    return "$releasever" if release == "stable" else release


def _dedupe(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def _enabled(value: bool | str) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "yes", "true", "on", "enabled"}


def _normalize_wms(values: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
    if values is None:
        raw: list[str] = []
    elif isinstance(values, str):
        raw = [part for part in re.split(r"[\s,]+", values.strip()) if part]
    else:
        raw = list(values)
    clean: list[str] = []
    for wm in raw:
        if wm not in VALID_WMS:
            raise ValueError(f"Unsupported window manager for Fedora: {wm}")
        clean.append(wm)
    return _dedupe(clean)


def recommended_display_manager(desktop: str, wms: tuple[str, ...], requested: str) -> str:
    if requested != "auto":
        return requested
    if desktop == "gnome":
        return "gdm"
    if desktop in {"plasma", "lxqt"}:
        return "sddm"
    if desktop in {"xfce", "mate"}:
        return "lightdm"
    return "greetd" if wms else "none"


def recommended_session(desktop: str, wms: tuple[str, ...], requested: str) -> str:
    if requested != "auto":
        return requested
    if desktop != "none":
        return desktop
    return wms[0] if wms else "shell"


def plan_from_options(
    *,
    release: str,
    arch: str,
    desktop: str,
    display_manager: str,
    default_session: str,
    wms: list[str] | tuple[str, ...] | str | None,
    network: str,
    wifi: bool | str,
    bluetooth: bool | str,
    audio: str,
    browser: str,
    firmware: str,
    kernel: str,
    bootloader: str,
    auto_resize: bool | str,
    legacy_x11_drivers: bool | str,
    extra_packages: str = "",
) -> FedoraPlan:
    validate_release(release)
    if arch not in FEDORA_ARCHES:
        raise ValueError(f"Unsupported Fedora architecture: {arch}")
    if desktop not in FEDORA_DESKTOPS:
        raise ValueError(f"Unsupported Fedora desktop: {desktop}")
    if display_manager not in FEDORA_DISPLAY_MANAGERS:
        raise ValueError(f"Unsupported Fedora display manager: {display_manager}")
    if network not in {"networkmanager", "none"}:
        raise ValueError(f"Unsupported Fedora network backend: {network}")
    if audio not in {"pipewire", "alsa", "none"}:
        raise ValueError(f"Unsupported Fedora audio option: {audio}")
    if browser not in {"firefox-esr", "firefox", "chromium", "none"}:
        raise ValueError(f"Unsupported Fedora browser: {browser}")
    if firmware not in FEDORA_FIRMWARE:
        raise ValueError(f"Unsupported Fedora firmware option: {firmware}")
    if kernel not in FEDORA_KERNELS:
        raise ValueError(f"Unsupported Fedora kernel flavor: {kernel}")
    if bootloader not in FEDORA_BOOTLOADERS:
        raise ValueError(f"Unsupported Fedora bootloader: {bootloader}")

    wm_tuple = _normalize_wms(wms)
    dm = recommended_display_manager(desktop, wm_tuple, display_manager)
    session = recommended_session(desktop, wm_tuple, default_session)
    valid_sessions = {*FEDORA_DESKTOPS, *VALID_WMS, "shell"} - {"none"}
    if session not in valid_sessions:
        raise ValueError(f"Unsupported Fedora default session: {session}")

    packages = [
        "basesystem",
        "systemd",
        "systemd-udev",
        "passwd",
        "sudo",
        "shadow-utils",
        "dnf",
        "vim-minimal",
        "bash",
        "coreutils",
        "util-linux",
        "e2fsprogs",
        "dosfstools",
        "parted",
        "tar",
        "rsync",
        "curl",
        "ca-certificates",
        "tzdata",
        "glibc-langpack-en",
        "kbd",
        "grub2-efi-x64",
        "shim-x64",
        "efibootmgr",
    ]
    groups = ["core"]
    services = ["systemd-timesyncd.service"]
    warnings: list[str] = []

    if kernel == "lts":
        packages.append("kernel")
        warnings.append("Fedora does not ship an official LTS kernel in default repositories; using kernel.")
    else:
        packages.append("kernel")
    if bootloader == "systemd-boot":
        packages.append("systemd-boot-unsigned")
    if _enabled(auto_resize):
        packages.extend(["cloud-utils-growpart", "gdisk"])
    if firmware == "full":
        packages.append("linux-firmware")

    graphical = desktop != "none" or bool(wm_tuple) or dm not in {"none", "greetd"}
    if graphical:
        groups.append("base-x")
        packages.extend(["xorg-x11-server-Xorg", "xorg-x11-xinit", "xkeyboard-config", "libinput", "mesa-dri-drivers"])
        if _enabled(legacy_x11_drivers):
            packages.extend(
                [
                    "xorg-x11-drv-amdgpu",
                    "xorg-x11-drv-ati",
                    "xorg-x11-drv-intel",
                    "xorg-x11-drv-nouveau",
                    "xorg-x11-drv-vesa",
                ]
            )

    desktop_groups = {
        "xfce": "xfce-desktop-environment",
        "gnome": "workstation-product-environment",
        "plasma": "kde-desktop-environment",
        "mate": "mate-desktop-environment",
        "lxqt": "lxqt-desktop-environment",
    }
    if desktop in desktop_groups:
        groups.append(desktop_groups[desktop])

    wm_packages = {
        "i3": ["i3", "i3status", "i3lock", "dmenu", "xterm"],
        "sway": [
            "sway",
            "swaybg",
            "swayidle",
            "swaylock",
            "foot",
            "waybar",
            "mako",
            "grim",
            "slurp",
            "xorg-x11-server-Xwayland",
        ],
        "hyprland": ["hyprland", "foot", "waybar", "mako", "xorg-x11-server-Xwayland"],
        "awesome": ["awesome", "xterm", "rofi"],
        "bspwm": ["bspwm", "sxhkd", "polybar", "xterm", "dmenu"],
        "openbox": ["openbox", "tint2", "xterm", "dmenu"],
        "labwc": ["labwc", "foot", "waybar", "mako"],
    }
    for wm in wm_tuple:
        packages.extend(wm_packages[wm])

    dm_packages = {
        "lightdm": ["lightdm", "lightdm-gtk"],
        "sddm": ["sddm"],
        "gdm": ["gdm"],
        "lxdm": ["lxdm"],
        "greetd": ["greetd", "greetd-tuigreet"],
    }
    if dm in dm_packages:
        packages.extend(dm_packages[dm])
        services.append(f"{dm}.service" if dm != "lightdm" else "lightdm.service")

    if network == "networkmanager":
        packages.append("NetworkManager")
        services.append("NetworkManager.service")
        if _enabled(wifi):
            packages.extend(["wpa_supplicant", "wireless-regdb"])
    if _enabled(bluetooth):
        packages.extend(["bluez", "bluez-tools"])
        services.append("bluetooth.service")
    if audio == "pipewire":
        packages.extend(["pipewire", "wireplumber", "pipewire-pulseaudio", "alsa-utils"])
    elif audio == "alsa":
        packages.append("alsa-utils")
    if browser == "firefox-esr":
        packages.append("firefox")
        warnings.append("Fedora default repositories provide firefox, not firefox-esr; using firefox.")
    elif browser != "none":
        packages.append(browser)

    for pkg in [part for part in re.split(r"\s+", extra_packages.strip()) if part]:
        packages.append(validate_package_name(pkg))

    return FedoraPlan(
        release=release,
        arch=arch,
        packages=_dedupe(packages),
        groups=_dedupe(groups),
        enabled_services=_dedupe(services),
        default_target="graphical.target" if graphical else "multi-user.target",
        display_manager=dm,
        default_session=session,
        warnings=tuple(warnings),
    )
