from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from alpine_usb.interfaces import cli


def namespace(**overrides) -> argparse.Namespace:
    values = {
        "profile": "compatibility",
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


def test_split_packages_rejects_invalid_package() -> None:
    with pytest.raises(ValueError, match="Invalid package"):
        cli.split_packages(["valid bad/name"], None)


def test_env_from_build_args_maps_namespace_to_build_environment() -> None:
    env = cli.env_from_build_args(namespace())

    assert env["ALPINE_BRANCH"] == "latest-stable"
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


def test_build_scripts_do_not_leak_spaced_env_into_docker_image() -> None:
    """Regression: extra packages with spaces (e.g. "vivaldi neovim kitty docker")
    must never word-split into a docker IMAGE positional.

    Earlier build-arch-usb.sh built ``docker_env`` as an unquoted string of
    ``-e NAME=value`` tokens and passed it to ``docker run``. When a value
    contained spaces (ALPINE_USB_EXTRA_PACKAGES), word splitting pushed the
    second package name into the image slot and docker tried to pull
    ``neovim:latest``. Every build script that calls ``docker run`` must use
    ``--env-file`` or a quoted ``"${docker_env[@]}"`` array so spaced values
    stay intact, and must never expand a bare ``$docker_env`` string.
    """
    import re

    repo = Path(__file__).resolve().parents[1]
    scripts = sorted(repo.glob("build-*-usb.sh"))
    assert scripts, "expected at least one build-*-usb.sh script"
    failures: list[str] = []
    for script in scripts:
        text = script.read_text()
        if "docker run" not in text:
            continue  # script never shells out to docker
        safe = ("--env-file" in text) or ('"${docker_env[@]}"' in text)
        # Bare $docker_env (not ${docker_env[@]} array, not $docker_env_file)
        # word-splits spaced values into docker positionals.
        leaks_unquoted = re.search(r"\$docker_env(?![A-Za-z0-9_@])", text) is not None
        if not safe or leaks_unquoted:
            failures.append(script.name)
    assert not failures, (
        "build-*-usb.sh docker run must use --env-file or quoted "
        '"${docker_env[@]}" array, never bare $docker_env: ' + ", ".join(failures)
    )


def test_build_arch_usb_passes_extra_packages_via_env_file() -> None:
    """build-arch-usb.sh must pass ALPINE_USB_EXTRA_PACKAGES through --env-file
    (not unquoted ``-e NAME=value``) so multi-word values survive intact."""
    repo = Path(__file__).resolve().parents[1]
    text = (repo / "build-arch-usb.sh").read_text()
    assert "--env-file" in text, "build-arch-usb.sh should use --env-file for env passthrough"
    assert 'docker_env="-e' not in text, "build-arch-usb.sh must not rebuild a flat -e string"


def test_prepare_terminal_runtime_copies_nested_builder_dockerfile(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ["build-alpine-usb.sh", "configure-alpine-usb.sh", "README.md", "LICENSE"]:
        (source / name).write_text(name)
    (source / "scripts").mkdir()
    (source / "scripts" / "Dockerfile.builder").write_text("FROM alpine")
    (source / "efi-fallback").mkdir()
    (source / "efi-fallback" / "BOOTX64.EFI").write_text("efi")
    monkeypatch.setattr(cli, "secure_runtime_dir", lambda name: tmp_path / "runtime")

    runtime = cli.prepare_terminal_runtime(source)

    assert (runtime / "scripts" / "Dockerfile.builder").read_text() == "FROM alpine"
    assert (runtime / "efi-fallback" / "BOOTX64.EFI").read_text() == "efi"
    assert (runtime / "build-alpine-usb.sh").exists()
