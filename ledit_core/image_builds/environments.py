from __future__ import annotations

import argparse
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from ledit_core.build_profiles.presets import VALID_WMS as BUILD_PROFILE_VALID_WMS
from ledit_core.linux_distros import DistroProvider, get_distro, rhel_variant_for_name
from ledit_core.linux_distros.fedora import plan_from_options as fedora_plan_from_options
from ledit_core.rhel_packages.packages import resolve_rhel_packages

ProviderLookup = Callable[[str | None], DistroProvider]
VALID_WMS = BUILD_PROFILE_VALID_WMS


def bool_env(value: bool) -> str:
    return "1" if value else "0"


def arg_was_passed(argv: list[str], name: str) -> bool:
    return any(token == name or token.startswith(name + "=") for token in argv)


def selected_provider(args: argparse.Namespace, provider_lookup: ProviderLookup = get_distro) -> DistroProvider:
    return provider_lookup(getattr(args, "distro", "alpine"))


def release_override(args: argparse.Namespace) -> str | None:
    return getattr(args, "release", None) or getattr(args, "nixos_channel", None)


def apply_distro_defaults(
    args: argparse.Namespace,
    argv: list[str],
    *,
    provider_lookup: ProviderLookup = get_distro,
) -> None:
    if getattr(args, "command", None) not in {"build", "search"}:
        return
    provider = selected_provider(args, provider_lookup)
    explicit_branch = arg_was_passed(argv, "--branch") or arg_was_passed(argv, "--release")
    explicit_user = arg_was_passed(argv, "--user")
    explicit_hostname = arg_was_passed(argv, "--hostname")
    explicit_output = arg_was_passed(argv, "--output") or arg_was_passed(argv, "-o")
    explicit_arch = arg_was_passed(argv, "--arch")
    args._explicit_user = explicit_user
    args._explicit_hostname = explicit_hostname
    args._explicit_output = explicit_output
    args._explicit_branch = explicit_branch
    args._explicit_arch = explicit_arch
    override = release_override(args)
    if override:
        args.branch = override
    elif provider.id != "alpine" and not explicit_branch:
        args.branch = provider.default_branch
    if getattr(args, "command", None) == "build":
        if provider.id != "alpine" and not explicit_user:
            args.user = provider.default_user
        if provider.id != "alpine" and not explicit_hostname:
            args.hostname = provider.default_hostname
        if not explicit_arch:
            args.arch = provider.default_arch
        if not explicit_output:
            default_output_dir = getattr(args, "default_output_dir", Path(tempfile.gettempdir()) / "ledit")
            args.output = str(default_output_dir / provider.default_image_name)
        if (
            provider.supports_extlinux
            and getattr(args, "bootloader", "grub") == "grub"
            and not arg_was_passed(argv, "--bootloader")
        ):
            args.bootloader = "extlinux"


def split_packages(
    values: list[str] | None,
    inline: str | None,
    distro: str = "alpine",
    *,
    provider_lookup: ProviderLookup = get_distro,
) -> str:
    provider = provider_lookup(distro)
    packages: list[str] = []
    for item in values or []:
        packages.extend(part for part in re.split(r"\s+", item.strip()) if part)
    if inline:
        packages.extend(part for part in re.split(r"\s+", inline.strip()) if part)
    deduped: list[str] = []
    seen: set[str] = set()
    for pkg in packages:
        provider.validate_package_name(pkg)
        if pkg not in seen:
            seen.add(pkg)
            deduped.append(pkg)
    return " ".join(deduped)


def ordered_wms(args: argparse.Namespace) -> list[str]:
    wms = list(getattr(args, "wm", None) or [])
    tiling_wms = getattr(args, "tiling_wms", "") or ""
    if tiling_wms:
        wms.extend(part for part in re.split(r"[\s,]+", tiling_wms.strip()) if part)
    ordered: list[str] = []
    for wm in wms:
        if wm not in ordered:
            ordered.append(wm)
    return ordered


def common_env(args: argparse.Namespace, prefix: str, extra_packages: str) -> dict[str, str]:
    password = getattr(args, "password", "") or ""
    root_password = (
        getattr(args, "root_password", None) if getattr(args, "root_password", None) is not None else password
    )
    return {
        f"{prefix}_PROFILE": getattr(args, "profile", "compatibility"),
        f"{prefix}_USER": args.user,
        f"{prefix}_PASSWORD": password,
        f"{prefix}_ROOT_PASSWORD": root_password,
        f"{prefix}_HOSTNAME": args.hostname,
        f"{prefix}_TIMEZONE": args.timezone,
        f"{prefix}_LOCALE": args.locale,
        f"{prefix}_LANGUAGE": args.language or "",
        f"{prefix}_CONSOLE_KEYMAP": args.console_keymap,
        f"{prefix}_XKB_LAYOUT": args.xkb_layout,
        f"{prefix}_XKB_VARIANT": args.xkb_variant,
        f"{prefix}_XKB_MODEL": args.xkb_model,
        f"{prefix}_DESKTOP": args.desktop,
        f"{prefix}_TILING_WMS": " ".join(ordered_wms(args)),
        f"{prefix}_DEFAULT_SESSION": args.default_session,
        f"{prefix}_DISPLAY_MANAGER": args.display_manager,
        f"{prefix}_NETWORK": args.network,
        f"{prefix}_WIFI": bool_env(args.wifi),
        f"{prefix}_BLUETOOTH": bool_env(args.bluetooth),
        f"{prefix}_AUDIO": args.audio,
        f"{prefix}_BROWSER": args.browser,
        f"{prefix}_FIRMWARE": args.firmware,
        f"{prefix}_LEGACY_X11_DRIVERS": bool_env(getattr(args, "legacy_x11_drivers", True)),
        f"{prefix}_BOOTLOADER": args.bootloader,
        f"{prefix}_KERNEL_FLAVOR": args.kernel,
        f"{prefix}_BOOT_TIMEOUT": str(args.boot_timeout),
        f"{prefix}_SYSTEMD_BOOT_CONSOLE_MODE": args.systemd_boot_console_mode,
        f"{prefix}_AUTO_RESIZE": bool_env(args.auto_resize),
        f"{prefix}_EXTRA_PACKAGES": extra_packages,
    }


def normalize_identity_defaults(args: argparse.Namespace, provider: DistroProvider) -> None:
    if provider.id == "alpine":
        return
    if not getattr(args, "_explicit_user", False) and getattr(args, "user", "alpine") == "alpine":
        args.user = provider.default_user
    if not getattr(args, "_explicit_hostname", False) and getattr(args, "hostname", "ledit-linux") == "ledit-linux":
        args.hostname = provider.default_hostname
    if not getattr(args, "_explicit_arch", False) and getattr(args, "arch", "x86_64") == "x86_64":
        args.arch = provider.default_arch


def env_from_build_args(
    args: argparse.Namespace,
    *,
    provider_lookup: ProviderLookup = get_distro,
) -> dict[str, str]:
    provider = selected_provider(args, provider_lookup)
    normalize_identity_defaults(args, provider)
    branch = provider.normalize_branch(getattr(args, "branch", provider.default_branch))
    arch = provider.normalize_arch(getattr(args, "arch", provider.default_arch))
    if args.bootloader == "extlinux" and not provider.supports_extlinux:
        raise ValueError(f"{provider.label} does not support extlinux from LEDIT; choose grub or systemd-boot")
    if args.bootloader == "systemd-boot" and not provider.supports_systemd_boot:
        raise ValueError(f"{provider.label} backend currently supports GRUB only; choose --bootloader grub")

    extra_packages = split_packages(
        args.extra_package, args.extra_packages, provider.id, provider_lookup=provider_lookup
    )
    env: dict[str, str] = {
        "IMAGE_NAME": f".{provider.id}-usb-cli-{os.getpid()}.img",
        "IMAGE_SIZE": args.image_size,
        "ARCH": arch,
        "LINUX_USB_DISTRO": provider.id,
        "LEDIT_DISTRO": provider.id,
        provider.branch_env: branch,
    }
    if provider.id == "alpine":
        env["ALPINE_BRANCH"] = branch
    elif provider.id == "void":
        env["VOID_USB_EXTRA_PACKAGES"] = extra_packages
    elif provider.id == "rhel":
        env["RHEL_USB_DISTRO"] = rhel_variant_for_name(getattr(args, "distro", "rhel"))
    elif provider.id == "arch":
        env["ARCH_USB_BRANCH"] = branch
    elif provider.id == "nixos":
        env["NIXOS_CHANNEL"] = branch

    env.update(common_env(args, provider.script_prefix, extra_packages))
    if provider.env_prefix != provider.script_prefix:
        env.update(common_env(args, provider.env_prefix, extra_packages))

    if provider.id == "fedora":
        plan = fedora_plan_from_options(
            release=branch,
            arch=arch,
            desktop=args.desktop,
            display_manager=args.display_manager,
            default_session=args.default_session,
            wms=ordered_wms(args),
            network=args.network,
            wifi=args.wifi,
            bluetooth=args.bluetooth,
            audio=args.audio,
            browser=args.browser,
            firmware=args.firmware,
            kernel=args.kernel,
            bootloader=args.bootloader,
            auto_resize=args.auto_resize,
            legacy_x11_drivers=getattr(args, "legacy_x11_drivers", True),
            extra_packages=extra_packages,
        )
        env.update(
            {
                "FEDORA_RELEASE": plan.release,
                "FEDORA_USB_PACKAGES": " ".join(plan.packages),
                "FEDORA_USB_GROUPS": " ".join(plan.groups),
                "FEDORA_USB_SERVICES": " ".join(plan.enabled_services),
                "FEDORA_USB_DEFAULT_TARGET": plan.default_target,
                "FEDORA_USB_WARNINGS": "\n".join(plan.warnings),
                "FEDORA_USB_DISPLAY_MANAGER": plan.display_manager,
                "FEDORA_USB_DEFAULT_SESSION": plan.default_session,
            }
        )
    elif provider.id == "rhel":
        env["RHEL_USB_PACKAGE_LIST"] = " ".join(
            resolve_rhel_packages(
                desktop=args.desktop,
                display_manager=args.display_manager,
                wms=ordered_wms(args),
                network=args.network,
                wifi=args.wifi,
                bluetooth=args.bluetooth,
                audio=args.audio,
                browser=args.browser,
                firmware=args.firmware,
                auto_resize=args.auto_resize,
                extra_packages=extra_packages,
            )
        )
    return env


def build_summary_rows(env: dict[str, str], *, provider_lookup: ProviderLookup = get_distro) -> list[tuple[str, str]]:
    provider = provider_lookup(env.get("LINUX_USB_DISTRO", "alpine"))
    prefix = provider.script_prefix
    branch = env.get(provider.branch_env) or env.get("ALPINE_BRANCH") or provider.default_branch
    return [
        ("Minimum image size", env["IMAGE_SIZE"]),
        ("Distribution", f"{provider.label} {branch} / {env['ARCH']}"),
        ("Profile", env.get(f"{prefix}_PROFILE", "compatibility")),
        ("Desktop", env[f"{prefix}_DESKTOP"]),
        ("Window managers", env[f"{prefix}_TILING_WMS"] or "none"),
        ("Default session", env[f"{prefix}_DEFAULT_SESSION"]),
        ("Display manager", env[f"{prefix}_DISPLAY_MANAGER"]),
        ("Network", f"{env[f'{prefix}_NETWORK']} wifi={env[f'{prefix}_WIFI']} bluetooth={env[f'{prefix}_BLUETOOTH']}"),
        ("Audio / browser", f"{env[f'{prefix}_AUDIO']} / {env[f'{prefix}_BROWSER']}"),
        (
            "Boot",
            f"{env[f'{prefix}_BOOTLOADER']} linux-{env[f'{prefix}_KERNEL_FLAVOR']} firmware={env[f'{prefix}_FIRMWARE']}",
        ),
        ("Legacy X11 drivers", env.get(f"{prefix}_LEGACY_X11_DRIVERS", "1")),
        ("Auto-resize USB", env[f"{prefix}_AUTO_RESIZE"]),
        ("Keyboard", f"console={env[f'{prefix}_CONSOLE_KEYMAP']} xkb={env[f'{prefix}_XKB_LAYOUT']}"),
        ("Extra packages", env[f"{prefix}_EXTRA_PACKAGES"] or "none"),
    ]
