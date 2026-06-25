from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ledit_core.apt_packages import index as apt_index
from ledit_core.interfaces import cli
from ledit_core.linux_distros import DISTROS, distro_choices, get_distro, registry
from ledit_core.linux_distros import providers as providers_facade

REPO_ROOT = Path(__file__).resolve().parents[2]


def namespace(**overrides) -> argparse.Namespace:
    provider = get_distro(overrides.get("distro", "alpine"))
    values = {
        "profile": "compatibility",
        "image_size": "16G",
        "distro": provider.id,
        "branch": provider.default_branch,
        "release": None,
        "nixos_channel": None,
        "arch": provider.default_arch,
        "user": provider.default_user,
        "password": "secret",
        "root_password": None,
        "hostname": provider.default_hostname,
        "timezone": "UTC",
        "locale": "en_US.UTF-8",
        "language": "",
        "console_keymap": "us",
        "xkb_layout": "us",
        "xkb_variant": "",
        "xkb_model": "pc105",
        "desktop": "xfce",
        "wm": ["i3"],
        "tiling_wms": "",
        "default_session": "auto",
        "display_manager": "auto",
        "network": "networkmanager",
        "wifi": True,
        "bluetooth": True,
        "audio": "pipewire",
        "browser": "firefox",
        "firmware": "full",
        "legacy_x11_drivers": True,
        "bootloader": "extlinux" if provider.supports_extlinux else "grub",
        "kernel": "lts",
        "boot_timeout": 3,
        "systemd_boot_console_mode": "max",
        "auto_resize": True,
        "extra_package": ["vim" if provider.id != "gentoo" else "app-editors/vim"],
        "extra_packages": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_registry_contains_all_workspace_distros() -> None:
    assert set(distro_choices(visible_only=True)) == {
        "alpine",
        "arch",
        "debian",
        "fedora",
        "gentoo",
        "nixos",
        "opensuse",
        "rhel",
        "slackware",
        "ubuntu",
        "void",
    }


def test_provider_facade_uses_modular_registry() -> None:
    assert providers_facade.DISTROS is registry.DISTROS
    assert get_distro("ubuntu").validate_package_func.__module__ == "ledit_core.deb_packages.index"
    assert apt_index.validate_package_name.__module__ == "ledit_core.apt_packages.index"


@pytest.mark.parametrize("distro", sorted(DISTROS))
def test_provider_build_scripts_exist_or_are_python_backed(distro: str) -> None:
    provider = get_distro(distro)
    assert provider.branch_choices
    if provider.build_script:
        assert (REPO_ROOT / provider.build_script).is_file()
    else:
        assert distro == "nixos"


@pytest.mark.parametrize("distro", sorted(DISTROS))
def test_cli_env_maps_each_distro_to_its_branch_and_prefix(distro: str) -> None:
    provider = get_distro(distro)
    env = cli.env_from_build_args(namespace(distro=distro))

    assert env["LINUX_USB_DISTRO"] == provider.id
    assert env[provider.branch_env] == provider.normalize_branch(provider.default_branch)
    assert env[f"{provider.script_prefix}_USER"] == provider.default_user
    assert env[f"{provider.script_prefix}_HOSTNAME"] == provider.default_hostname
    assert env[f"{provider.script_prefix}_EXTRA_PACKAGES"]


def test_cli_env_populates_package_plans_for_dnf_backends() -> None:
    fedora_env = cli.env_from_build_args(namespace(distro="fedora", desktop="none", display_manager="none"))
    rhel_env = cli.env_from_build_args(namespace(distro="rhel", desktop="none", display_manager="none"))

    assert "kernel" in fedora_env["FEDORA_USB_PACKAGES"]
    assert "@core" in rhel_env["RHEL_USB_PACKAGE_LIST"]


def test_split_packages_uses_selected_distro_validator() -> None:
    assert cli.split_packages(["app-editors/vim"], None, "gentoo") == "app-editors/vim"
    with pytest.raises(ValueError, match="Invalid"):
        cli.split_packages(["bad/package"], None, "slackware")
