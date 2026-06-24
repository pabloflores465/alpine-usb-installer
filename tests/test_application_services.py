from __future__ import annotations

import argparse
from pathlib import Path

from ledit_core.application import (
    BuildImageService,
    BuildRequest,
    DoctorService,
    FlashImageService,
    HostCheck,
    build_request_from_namespace,
    build_request_to_env,
)
from ledit_core.image_builds.execution import BuildResult
from ledit_core.images.validation import ImageValidation
from ledit_core.interfaces import cli


def namespace(**overrides) -> argparse.Namespace:
    values = {
        "profile": "compatibility",
        "distro": "alpine",
        "output": "ledit.img",
        "image_size": "16G",
        "branch": "latest-stable",
        "release": None,
        "nixos_channel": None,
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


def test_build_request_adapter_preserves_existing_env_contract() -> None:
    args = namespace()
    request = build_request_from_namespace(args)

    assert request.desktop.window_managers == ("i3", "sway", "openbox")
    assert build_request_to_env(request) == cli.env_from_build_args(args)


def test_build_request_preserves_rhel_alias_for_variant_env() -> None:
    args = namespace(distro="alma", branch="9", extra_package=["vim"], extra_packages="")

    assert build_request_to_env(build_request_from_namespace(args))["RHEL_USB_DISTRO"] == "alma"


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, str], Path]] = []

    def run(self, config_env: dict[str, str], output_path: str | Path, log=None) -> BuildResult:
        self.calls.append((config_env, Path(output_path)))
        if log:
            log("fake build log")
        return BuildResult(True, f"built {output_path}")

    def cancel(self, log=None) -> None:
        if log:
            log("cancelled")

    def force_cancel(self, log=None) -> None:
        if log:
            log("force cancelled")


def test_build_image_service_uses_build_request_and_injected_runner(tmp_path: Path) -> None:
    runner = FakeRunner()
    service = BuildImageService(runtime_root=tmp_path, default_output_dir=tmp_path, runner_factory=lambda: runner)
    plan = service.plan_from_namespace(namespace(output=str(tmp_path / "out.img")))
    logs: list[str] = []

    result = service.execute(plan, log=logs.append)

    assert result.ok
    assert logs == ["fake build log"]
    assert runner.calls[0][0]["LEDIT_USB_EXTRA_PACKAGES"] == "vim htop neovim"
    assert runner.calls[0][1] == tmp_path / "out.img"


def test_build_image_service_dry_run_runner_is_injectable(tmp_path: Path) -> None:
    seen: list[tuple[dict[str, str], Path]] = []

    def dry_run(env: dict[str, str], root: Path) -> int:
        seen.append((env, root))
        return 7

    service = BuildImageService(runtime_root=tmp_path, dry_run_runner=dry_run)
    plan = service.plan(BuildRequest())

    assert service.run_dry_run(plan) == 7
    assert seen == [(plan.env, tmp_path)]


def test_flash_image_service_plans_and_executes_linux_without_real_dd(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "usb.img"
    image.write_bytes(b"not real gpt; validation is mocked")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        "ledit_core.application.services.validate_usb_image",
        lambda _path: ImageValidation(True, size=image.stat().st_size),
    )
    monkeypatch.setattr(
        "ledit_core.application.services.device_safety_report",
        lambda dev: (True, dev, [("Target", dev), ("Model", "USB")], None),
    )
    monkeypatch.setattr("ledit_core.application.services.platform.system", lambda: "Linux")
    monkeypatch.setattr("ledit_core.application.services.os.geteuid", lambda: 0)
    monkeypatch.setattr("ledit_core.application.services.subprocess.call", lambda cmd: calls.append(cmd) or 0)

    service = FlashImageService()
    plan = service.plan(image, "/dev/sdz")

    assert plan.device == "/dev/sdz"
    assert service.execute(plan) == 0
    assert calls == [
        ["dd", f"if={image.resolve()}", "of=/dev/sdz", "bs=16M", "iflag=fullblock", "status=progress", "conv=fsync"]
    ]


def test_doctor_failed_ignores_optional_checks() -> None:
    service = DoctorService()

    assert service.failed([HostCheck("required", False), HostCheck("optional nix", False, required=False)])
    assert not service.failed([HostCheck("optional nix", False, required=False), HostCheck("dd", True)])
