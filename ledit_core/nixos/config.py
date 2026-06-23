from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from ledit_core.build_profiles.presets import VALID_WMS
from ledit_core.nixos.packages import NIXOS_DEFAULT_CHANNEL, validate_nix_channel, validate_nix_package_name

NIXOS_DESKTOPS = ("xfce", "gnome", "plasma", "mate", "lxqt", "none")
NIXOS_DISPLAY_MANAGERS = ("auto", "lightdm", "sddm", "gdm", "lxdm", "greetd", "none")
NIXOS_SESSIONS = ("auto", *NIXOS_DESKTOPS[:-1], *VALID_WMS, "shell")
NIXOS_BROWSERS = ("firefox", "chromium", "none")
NIXOS_AUDIO = ("pipewire", "alsa", "none")
NIXOS_KERNELS = ("lts", "stable")
NIXOS_BOOTLOADERS = ("extlinux", "grub", "systemd-boot")


@dataclass(frozen=True)
class NixosBuildConfig:
    channel: str = NIXOS_DEFAULT_CHANNEL
    arch: str = "x86_64-linux"
    hostname: str = "ledit-nixos"
    user: str = "nixos"
    password: str = ""
    root_password: str = ""
    timezone: str = "UTC"
    locale: str = "en_US.UTF-8"
    console_keymap: str = "us"
    xkb_layout: str = "us"
    xkb_variant: str = ""
    xkb_model: str = "pc105"
    desktop: str = "xfce"
    display_manager: str = "auto"
    default_session: str = "auto"
    window_managers: tuple[str, ...] = ()
    browser: str = "firefox"
    audio: str = "pipewire"
    network: str = "networkmanager"
    wifi: bool = True
    bluetooth: bool = True
    bootloader: str = "extlinux"
    kernel: str = "lts"
    firmware: str = "full"
    auto_resize: bool = True
    extra_packages: tuple[str, ...] = field(default_factory=tuple)


def _nix_bool(value: bool) -> str:
    return "true" if value else "false"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return tuple(ordered)


def config_from_args(args: argparse.Namespace, extra_packages: str) -> NixosBuildConfig:
    channel = getattr(args, "nixos_channel", None) or getattr(args, "branch", None) or NIXOS_DEFAULT_CHANNEL
    if channel == "latest-stable":
        channel = NIXOS_DEFAULT_CHANNEL
    validate_nix_channel(channel)
    arg_arch = getattr(args, "arch", "x86_64")
    arch = "x86_64-linux" if arg_arch in {"x86_64", "x86_64-linux"} else arg_arch
    if arch != "x86_64-linux":
        raise ValueError("NixOS backend currently supports x86_64-linux images only")
    packages = tuple(part for part in extra_packages.split() if part)
    for package in packages:
        validate_nix_package_name(package)
    wms = list(getattr(args, "wm", None) or [])
    tiling = getattr(args, "tiling_wms", "") or ""
    wms.extend(part for part in tiling.replace(",", " ").split() if part)
    for wm in wms:
        if wm not in VALID_WMS:
            raise ValueError(f"Unsupported NixOS window manager: {wm}")
    password = getattr(args, "password", "") or ""
    root_password = getattr(args, "root_password", None) or password
    return NixosBuildConfig(
        channel=channel,
        arch=arch,
        hostname=getattr(args, "hostname", "ledit-nixos"),
        user=getattr(args, "user", "nixos"),
        password=password,
        root_password=root_password,
        timezone=getattr(args, "timezone", "UTC"),
        locale=getattr(args, "locale", "en_US.UTF-8"),
        console_keymap=getattr(args, "console_keymap", "us"),
        xkb_layout=getattr(args, "xkb_layout", "us"),
        xkb_variant=getattr(args, "xkb_variant", ""),
        xkb_model=getattr(args, "xkb_model", "pc105"),
        desktop=getattr(args, "desktop", "xfce"),
        display_manager=getattr(args, "display_manager", "auto"),
        default_session=getattr(args, "default_session", "auto"),
        window_managers=_ordered_unique(wms),
        browser=getattr(args, "browser", "firefox"),
        audio=getattr(args, "audio", "pipewire"),
        network=getattr(args, "network", "networkmanager"),
        wifi=bool(getattr(args, "wifi", True)),
        bluetooth=bool(getattr(args, "bluetooth", True)),
        bootloader=getattr(args, "bootloader", "extlinux"),
        kernel=getattr(args, "kernel", "lts"),
        firmware=getattr(args, "firmware", "full"),
        auto_resize=bool(getattr(args, "auto_resize", True)),
        extra_packages=packages,
    )


def _package_exprs(config: NixosBuildConfig) -> list[str]:
    packages = [*config.extra_packages]
    if config.browser != "none":
        packages.append("firefox" if config.browser == "firefox" else config.browser)
    wm_packages = {
        "i3": "i3",
        "sway": "sway",
        "hyprland": "hyprland",
        "awesome": "awesome",
        "bspwm": "bspwm",
        "openbox": "openbox",
        "labwc": "labwc",
    }
    packages.extend(wm_packages[wm] for wm in config.window_managers if wm in wm_packages)
    return _ordered_unique(packages)


def _desktop_lines(config: NixosBuildConfig) -> list[str]:
    lines = ["  services.xserver.enable = true;"]
    if config.desktop == "xfce":
        lines.append("  services.xserver.desktopManager.xfce.enable = true;")
    elif config.desktop == "gnome":
        lines.append("  services.xserver.desktopManager.gnome.enable = true;")
    elif config.desktop == "plasma":
        lines.append("  services.desktopManager.plasma6.enable = true;")
    elif config.desktop == "mate":
        lines.append("  services.xserver.desktopManager.mate.enable = true;")
    elif config.desktop == "lxqt":
        lines.append("  services.xserver.desktopManager.lxqt.enable = true;")
    dm = config.display_manager
    if dm == "auto":
        dm = {"gnome": "gdm", "plasma": "sddm", "lxqt": "sddm", "none": "none"}.get(config.desktop, "lightdm")
    if dm == "lightdm":
        lines.append("  services.xserver.displayManager.lightdm.enable = true;")
    elif dm == "sddm":
        lines.append("  services.displayManager.sddm.enable = true;")
    elif dm == "gdm":
        lines.append("  services.xserver.displayManager.gdm.enable = true;")
    elif dm == "lxdm":
        lines.append("  services.xserver.displayManager.lxdm.enable = true;")
    elif dm == "greetd":
        lines.append("  services.greetd.enable = true;")
    return lines


def generate_configuration_nix(config: NixosBuildConfig) -> str:
    package_exprs = " ".join(f"pkgs.{package}" for package in _package_exprs(config))
    desktop_lines = [] if config.desktop == "none" and not config.window_managers else _desktop_lines(config)
    kernel = "pkgs.linuxPackages" if config.kernel == "lts" else "pkgs.linuxPackages_latest"
    lines = [
        "{ config, lib, pkgs, modulesPath, ... }:",
        "{",
        '  imports = [ (modulesPath + "/installer/sd-card/sd-image-x86_64.nix") ];',
        f"  networking.hostName = {_quote(config.hostname)};",
        f"  time.timeZone = {_quote(config.timezone)};",
        f"  i18n.defaultLocale = {_quote(config.locale)};",
        f"  console.keyMap = {_quote(config.console_keymap)};",
        "  services.xserver.xkb = {",
        f"    layout = {_quote(config.xkb_layout)};",
        f"    variant = {_quote(config.xkb_variant)};",
        f"    model = {_quote(config.xkb_model)};",
        "  };",
        f"  boot.kernelPackages = {kernel};",
        f"  hardware.enableRedistributableFirmware = lib.mkForce {_nix_bool(config.firmware == 'full')};",
        f"  boot.growPartition = {_nix_bool(config.auto_resize)};",
        "  boot.loader.grub.enable = lib.mkForce " + _nix_bool(config.bootloader == "grub") + ";",
        "  boot.loader.systemd-boot.enable = lib.mkForce " + _nix_bool(config.bootloader == "systemd-boot") + ";",
        "  boot.loader.generic-extlinux-compatible.enable = lib.mkDefault "
        + _nix_bool(config.bootloader == "extlinux")
        + ";",
        "  boot.loader.efi.canTouchEfiVariables = false;",
        "  networking.networkmanager.enable = " + _nix_bool(config.network == "networkmanager") + ";",
        "  networking.wireless.enable = " + _nix_bool(config.wifi and config.network != "networkmanager") + ";",
        "  hardware.bluetooth.enable = " + _nix_bool(config.bluetooth) + ";",
        "  services.blueman.enable = " + _nix_bool(config.bluetooth) + ";",
        "  security.sudo.wheelNeedsPassword = false;",
        f"  users.users.{config.user} = {{",
        "    isNormalUser = true;",
        '    extraGroups = [ "wheel" "networkmanager" "audio" "video" ];',
        f"    initialPassword = {_quote(config.password)};",
        "  };",
        f"  users.users.root.initialPassword = {_quote(config.root_password)};",
    ]
    lines.extend(desktop_lines)
    if config.audio == "pipewire":
        # PipeWire provides a PulseAudio-compatible server via services.pipewire.pulse.
        # hardware.pulseaudio defaults to false on NixOS >= 24.11, so we do not
        # (and must not) reference the removed services.pulseaudio option.
        lines.extend(
            [
                "  security.rtkit.enable = true;",
                "  services.pipewire = { enable = true; alsa.enable = true; pulse.enable = true; };",
            ]
        )
    elif config.audio == "alsa":
        # The sound.enable option was removed in NixOS 25.05; ALSA stays in the
        # kernel by default, so emit nothing channel-specific here.
        pass
    if package_exprs:
        lines.append(f"  environment.systemPackages = with pkgs; [ {package_exprs} ];")
    else:
        lines.append("  environment.systemPackages = [ ];")
    lines.extend(
        [
            "  services.openssh.enable = true;",
            '  system.stateVersion = "24.11";',
            "}",
            "",
        ]
    )
    return "\n".join(lines)


def generate_flake_nix(config: NixosBuildConfig) -> str:
    return f"""{{
  description = "LEDIT generated NixOS image";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/{config.channel}";
  outputs = {{ self, nixpkgs }}: {{
    nixosConfigurations.usb = nixpkgs.lib.nixosSystem {{
      system = "{config.arch}";
      modules = [ ./configuration.nix ];
    }};
  }};
}}
"""
