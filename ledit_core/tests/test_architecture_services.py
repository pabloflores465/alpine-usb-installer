from __future__ import annotations

import argparse
import stat
from pathlib import Path

import pytest

from ledit_core.image_builds import environments as build_environments
from ledit_core.image_builds import runtime as build_runtime
from ledit_core.image_builds import secrets as build_secrets
from ledit_core.interfaces import cli
from ledit_core.linux_distros import DISTROS, get_distro
from ledit_core.linux_distros.models import DistroProvider
from ledit_core.package_search import DistroPackageSearchService, PackageSearchRequest


def namespace(**overrides) -> argparse.Namespace:
    values = {
        "profile": "compatibility",
        "image_size": "16G",
        "branch": "latest-stable",
        "arch": "x86_64",
        "user": "alpine",
        "password": "secret",
        "root_password": None,
        "hostname": "ledit-linux",
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


def test_cli_env_wrapper_delegates_to_image_build_environment() -> None:
    assert cli.env_from_build_args(namespace()) == build_environments.env_from_build_args(namespace())


def test_tui_frontend_does_not_depend_on_cli_frontend() -> None:
    tui_source = (Path(__file__).resolve().parents[1] / "frontends" / "tui" / "app.py").read_text()

    assert "frontends.cli" not in tui_source
    assert "cli.cmd_" not in tui_source
    assert "import cli" not in tui_source


def test_distro_provider_model_is_domain_boundary() -> None:
    assert isinstance(get_distro("alpine"), DistroProvider)


class FakeProvider:
    id = "fake"
    label = "Fake Linux"

    def validate_package_name(self, package: str) -> str:
        if "/" in package:
            raise ValueError("invalid package")
        return package

    def search_packages(self, _branch: str, _arch: str, query: str, _limit: int) -> list[dict[str, str]]:
        if query in {"vim", "nano"}:
            return [{"name": query, "repo": "main", "description": "found"}]
        return [{"name": f"{query}-doc", "repo": "docs", "description": "not an exact package match"}]

    def repo_description(self, branch: str, arch: str) -> str:
        return f"Fake Linux {branch}/{arch} repos"


def test_package_search_service_reports_missing_selected_packages_without_network() -> None:
    service = DistroPackageSearchService(lambda _name: FakeProvider())  # type: ignore[arg-type]

    assert service.repo_description("fake", "stable", "x86_64") == "Fake Linux stable/x86_64 repos"
    assert service.search(PackageSearchRequest("fake", "stable", "x86_64", "vim", 10))[0]["name"] == "vim"
    assert service.validate_selection("fake", "stable", "x86_64", ["vim", "ghost", "nano"]) == ["ghost"]
    with pytest.raises(ValueError, match="invalid package"):
        service.validate_selection("fake", "stable", "x86_64", ["bad/name"])


def test_secret_materializer_covers_all_distro_prefixes_and_cleans_files(tmp_path: Path) -> None:
    secret_env = {}
    for provider in DISTROS.values():
        for prefix in {provider.script_prefix, provider.env_prefix}:
            secret_env[f"{prefix}_PASSWORD"] = f"pw-{prefix}"
            secret_env[f"{prefix}_ROOT_PASSWORD"] = f"root-{prefix}"

    safe_env, files = build_secrets.prepare_secret_env(secret_env, tmp_path)

    assert files
    for key in secret_env:
        assert key not in safe_env
        file_key = f"{key}_FILE"
        assert file_key in safe_env
        path = Path(safe_env[file_key])
        assert path.read_text() == secret_env[key]
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    build_secrets.cleanup_secret_files(files)
    assert all(not path.exists() for path in files)


def test_runtime_workspace_copies_nested_assets_with_injected_workspace(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "ledit_core" / "backend" / "scripts").mkdir(parents=True)
    (source / "ledit_core" / "backend" / "scripts" / "build-alpine-usb.sh").write_text("#!/bin/sh\n")
    (source / "ledit_core" / "backend" / "docker").mkdir()
    (source / "ledit_core" / "backend" / "docker" / "Dockerfile.builder").write_text("FROM alpine")
    (source / "ledit_core" / "backend" / "efi-fallback").mkdir(parents=True)
    (source / "ledit_core" / "backend" / "efi-fallback" / "BOOTX64.EFI").write_text("efi")
    runtime = tmp_path / "runtime"

    result = build_runtime.prepare_runtime(
        source,
        "ignored",
        (
            "ledit_core/backend/scripts/build-alpine-usb.sh",
            "ledit_core/backend/docker/Dockerfile.builder",
            "ledit_core/backend/efi-fallback",
        ),
        secure_dir=lambda _name: runtime,
    )

    assert result == runtime
    assert (runtime / "ledit_core" / "backend" / "scripts" / "build-alpine-usb.sh").exists()
    assert (runtime / "ledit_core" / "backend" / "docker" / "Dockerfile.builder").read_text() == "FROM alpine"
    assert (runtime / "ledit_core" / "backend" / "efi-fallback" / "BOOTX64.EFI").read_text() == "efi"
    assert (runtime / ".work").is_dir()
