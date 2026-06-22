from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from alpine_usb.interfaces import cli


def namespace(**overrides) -> argparse.Namespace:
    values = {
        "profile": "compatibility",
        "distro": "alpine",
        "image_size": "16G",
        "branch": "latest-stable",
        "arch": "x86_64",
        "user": "alpine",
        "password": "secret",
        "root_password": None,
        "hostname": "alpine-usb",
        "timezone": "UTC",
        "locale": "en_US.UTF-8",
        "language": "",
        "console_keymap": "us",
        "xkb_layout": "us",
        "xkb_variant": "",
        "xkb_model": "pc105",
        "desktop": "xfce",
        "wm": ["i3", "i3"],
        "tiling_wms": "sway,openbox",
        "default_session": "auto",
        "display_manager": "auto",
        "network": "networkmanager",
        "wifi": True,
        "bluetooth": False,
        "audio": "pipewire",
        "browser": "firefox",
        "firmware": "full",
        "legacy_x11_drivers": False,
        "bootloader": "grub",
        "kernel": "lts",
        "boot_timeout": 3,
        "systemd_boot_console_mode": "max",
        "auto_resize": True,
        "extra_package": ["vim htop", "vim"],
        "extra_packages": "neovim",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_split_packages_dedupes_in_stable_order() -> None:
    assert cli.split_packages(["vim htop", "vim"], "neovim htop") == "vim htop neovim"


def test_split_packages_accepts_gentoo_category_atoms() -> None:
    assert (
        cli.split_packages(["www-client/firefox vim"], "app-misc/ranger", "gentoo")
        == "www-client/firefox vim app-misc/ranger"
    )


def test_split_packages_rejects_invalid_package() -> None:
    with pytest.raises(ValueError, match="Invalid package"):
        cli.split_packages(["valid bad/name"], None)


def test_env_from_build_args_maps_namespace_to_build_environment() -> None:
    env = cli.env_from_build_args(namespace())

    assert env["ALPINE_BRANCH"] == "latest-stable"
    assert env["ALPINE_USB_DISTRO"] == "alpine"
    assert env["ALPINE_USB_ROOT_PASSWORD"] == "secret"
    assert env["ALPINE_USB_TILING_WMS"] == "i3 sway openbox"
    assert env["ALPINE_USB_BLUETOOTH"] == "0"
    assert env["ALPINE_USB_LEGACY_X11_DRIVERS"] == "0"
    assert env["ALPINE_USB_EXTRA_PACKAGES"] == "vim htop neovim"


def test_prepare_secret_env_moves_passwords_to_files(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "repo_root", lambda: tmp_path)

    safe_env, files = cli.prepare_secret_env({"ALPINE_USB_PASSWORD": "pw", "ALPINE_USB_ROOT_PASSWORD": "rootpw"})

    assert "ALPINE_USB_PASSWORD" not in safe_env
    assert Path(safe_env["ALPINE_USB_PASSWORD_FILE"]).read_text() == "pw"
    assert Path(safe_env["ALPINE_USB_ROOT_PASSWORD_FILE"]).read_text() == "rootpw"
    assert len(files) == 2


def test_prepare_terminal_runtime_copies_nested_builder_dockerfile(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in [
        "build-alpine-usb.sh",
        "configure-alpine-usb.sh",
        "build-gentoo-usb.sh",
        "configure-gentoo-usb.sh",
        "README.md",
        "LICENSE",
    ]:
        (source / name).write_text(name)
    (source / "scripts").mkdir()
    (source / "scripts" / "Dockerfile.builder").write_text("FROM alpine")
    (source / "scripts" / "Dockerfile.gentoo-builder").write_text("FROM alpine-gentoo")
    (source / "efi-fallback").mkdir()
    (source / "efi-fallback" / "BOOTX64.EFI").write_text("efi")
    monkeypatch.setattr(cli, "secure_runtime_dir", lambda name: tmp_path / "runtime")

    runtime = cli.prepare_terminal_runtime(source)

    assert (runtime / "scripts" / "Dockerfile.builder").read_text() == "FROM alpine"
    assert (runtime / "scripts" / "Dockerfile.gentoo-builder").read_text() == "FROM alpine-gentoo"
    assert (runtime / "efi-fallback" / "BOOTX64.EFI").read_text() == "efi"
    assert (runtime / "build-alpine-usb.sh").exists()
    assert (runtime / "build-gentoo-usb.sh").exists()


def test_env_from_build_args_accepts_gentoo_branch_and_atoms() -> None:
    env = cli.env_from_build_args(
        namespace(distro="gentoo", branch="stable", user="gentoo", extra_packages="www-client/firefox")
    )

    assert env["ALPINE_USB_DISTRO"] == "gentoo"
    assert env["GENTOO_STAGE3_BRANCH"] == "stable"
    assert env["ALPINE_USB_EXTRA_PACKAGES"] == "vim htop www-client/firefox"
