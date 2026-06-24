from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ledit_core.image_builds import environments as build_environments
from ledit_core.linux_distros import DistroProvider, get_distro

ProviderLookup = Callable[[str | None], DistroProvider]


@dataclass(frozen=True)
class BuildTarget:
    distro: str = "alpine"
    branch: str = "latest-stable"
    arch: str = "x86_64"
    image_size: str = "16G"
    output_path: Path = Path("ledit.img")


@dataclass(frozen=True)
class UserConfig:
    username: str = "alpine"
    password: str = ""
    root_password: str | None = None
    hostname: str = "ledit-linux"


@dataclass(frozen=True)
class LocalizationConfig:
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    language: str = ""
    console_keymap: str = "us"
    xkb_layout: str = "us"
    xkb_variant: str = ""
    xkb_model: str = "pc105"


@dataclass(frozen=True)
class DesktopConfig:
    desktop: str = "xfce"
    display_manager: str = "auto"
    default_session: str = "auto"
    window_managers: tuple[str, ...] = field(default_factory=tuple)
    browser: str = "firefox"
    audio: str = "pipewire"


@dataclass(frozen=True)
class HardwareConfig:
    network: str = "networkmanager"
    wifi: bool = True
    bluetooth: bool = True
    firmware: str = "full"
    legacy_x11_drivers: bool = True


@dataclass(frozen=True)
class BootConfig:
    bootloader: str = "grub"
    kernel: str = "lts"
    boot_timeout: int = 3
    systemd_boot_console_mode: str = "max"
    auto_resize: bool = True


@dataclass(frozen=True)
class ExtraPackagesConfig:
    packages: tuple[str, ...] = field(default_factory=tuple)
    inline: str = ""


@dataclass(frozen=True)
class BuildRequest:
    profile: str = "compatibility"
    target: BuildTarget = field(default_factory=BuildTarget)
    user: UserConfig = field(default_factory=UserConfig)
    localization: LocalizationConfig = field(default_factory=LocalizationConfig)
    desktop: DesktopConfig = field(default_factory=DesktopConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    boot: BootConfig = field(default_factory=BootConfig)
    extra_packages: ExtraPackagesConfig = field(default_factory=ExtraPackagesConfig)


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value)  # type: ignore[operator]


def build_request_from_namespace(
    args: argparse.Namespace,
    *,
    output_path: str | Path | None = None,
    provider_lookup: ProviderLookup = get_distro,
) -> BuildRequest:
    provider = provider_lookup(getattr(args, "distro", "alpine"))
    branch = build_environments.release_override(args) or getattr(args, "branch", provider.default_branch)
    output = Path(output_path if output_path is not None else getattr(args, "output", provider.default_image_name))
    password = getattr(args, "password", "") or ""
    root_password = getattr(args, "root_password", None)
    return BuildRequest(
        profile=getattr(args, "profile", "compatibility"),
        target=BuildTarget(
            distro=getattr(args, "distro", provider.id),
            branch=branch,
            arch=getattr(args, "arch", provider.default_arch),
            image_size=getattr(args, "image_size", "16G"),
            output_path=output,
        ),
        user=UserConfig(
            username=getattr(args, "user", provider.default_user),
            password=password,
            root_password=root_password,
            hostname=getattr(args, "hostname", provider.default_hostname),
        ),
        localization=LocalizationConfig(
            timezone=getattr(args, "timezone", "UTC"),
            locale=getattr(args, "locale", "en_US.UTF-8"),
            language=getattr(args, "language", "") or "",
            console_keymap=getattr(args, "console_keymap", "us"),
            xkb_layout=getattr(args, "xkb_layout", "us"),
            xkb_variant=getattr(args, "xkb_variant", "") or "",
            xkb_model=getattr(args, "xkb_model", "pc105"),
        ),
        desktop=DesktopConfig(
            desktop=getattr(args, "desktop", "xfce"),
            display_manager=getattr(args, "display_manager", "auto"),
            default_session=getattr(args, "default_session", "auto"),
            window_managers=tuple(build_environments.ordered_wms(args)),
            browser=getattr(args, "browser", "firefox"),
            audio=getattr(args, "audio", "pipewire"),
        ),
        hardware=HardwareConfig(
            network=getattr(args, "network", "networkmanager"),
            wifi=bool(getattr(args, "wifi", True)),
            bluetooth=bool(getattr(args, "bluetooth", True)),
            firmware=getattr(args, "firmware", "full"),
            legacy_x11_drivers=bool(getattr(args, "legacy_x11_drivers", True)),
        ),
        boot=BootConfig(
            bootloader=getattr(args, "bootloader", "grub"),
            kernel=getattr(args, "kernel", "lts"),
            boot_timeout=int(getattr(args, "boot_timeout", 3) or 3),
            systemd_boot_console_mode=getattr(args, "systemd_boot_console_mode", "max"),
            auto_resize=bool(getattr(args, "auto_resize", True)),
        ),
        extra_packages=ExtraPackagesConfig(
            packages=_string_tuple(getattr(args, "extra_package", None)),
            inline=getattr(args, "extra_packages", "") or "",
        ),
    )


def namespace_from_build_request(request: BuildRequest) -> argparse.Namespace:
    return argparse.Namespace(
        profile=request.profile,
        distro=request.target.distro,
        output=str(request.target.output_path),
        image_size=request.target.image_size,
        branch=request.target.branch,
        release=None,
        nixos_channel=None,
        arch=request.target.arch,
        user=request.user.username,
        password=request.user.password,
        root_password=request.user.root_password,
        hostname=request.user.hostname,
        timezone=request.localization.timezone,
        locale=request.localization.locale,
        language=request.localization.language,
        console_keymap=request.localization.console_keymap,
        xkb_layout=request.localization.xkb_layout,
        xkb_variant=request.localization.xkb_variant,
        xkb_model=request.localization.xkb_model,
        desktop=request.desktop.desktop,
        display_manager=request.desktop.display_manager,
        default_session=request.desktop.default_session,
        wm=list(request.desktop.window_managers),
        tiling_wms="",
        browser=request.desktop.browser,
        audio=request.desktop.audio,
        network=request.hardware.network,
        wifi=request.hardware.wifi,
        bluetooth=request.hardware.bluetooth,
        firmware=request.hardware.firmware,
        legacy_x11_drivers=request.hardware.legacy_x11_drivers,
        bootloader=request.boot.bootloader,
        kernel=request.boot.kernel,
        boot_timeout=request.boot.boot_timeout,
        systemd_boot_console_mode=request.boot.systemd_boot_console_mode,
        auto_resize=request.boot.auto_resize,
        extra_package=list(request.extra_packages.packages),
        extra_packages=request.extra_packages.inline,
    )


def build_request_to_env(
    request: BuildRequest,
    *,
    provider_lookup: ProviderLookup = get_distro,
) -> dict[str, str]:
    return build_environments.env_from_build_args(
        namespace_from_build_request(request),
        provider_lookup=provider_lookup,
    )
