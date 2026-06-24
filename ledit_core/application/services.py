from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import ledit_core.application.runtime as app_runtime
from ledit_core.application.build_requests import BuildRequest, build_request_from_namespace, build_request_to_env
from ledit_core.image_builds.dry_runs import run_config_dry_run
from ledit_core.image_builds.execution import BuildLog, BuildResult, ImageBuildRunner, ScriptImageBuildRunner
from ledit_core.images.validation import validate_usb_image
from ledit_core.linux_distros import DistroProvider, get_distro
from ledit_core.usb_devices.detection import device_safety_report, list_devices, selected_device

RunnerFactory = Callable[[], ImageBuildRunner]
DryRunRunner = Callable[[dict[str, str], Path], int]


def default_runtime_root() -> Path:
    return app_runtime.terminal_runtime_root()


@dataclass(frozen=True)
class BuildPlan:
    request: BuildRequest
    env: dict[str, str]
    output_path: Path
    provider: DistroProvider


class BuildImageService:
    def __init__(
        self,
        *,
        runtime_root: Path | None = None,
        default_output_dir: Path | None = None,
        runner_factory: RunnerFactory | None = None,
        dry_run_runner: DryRunRunner = run_config_dry_run,
    ):
        self.runtime_root = runtime_root or default_runtime_root()
        self.default_output_dir = default_output_dir or (Path(tempfile.gettempdir()) / "ledit")
        self._runner_factory = runner_factory
        self._dry_run_runner = dry_run_runner

    def plan(self, request: BuildRequest) -> BuildPlan:
        env = build_request_to_env(request)
        provider = get_distro(env.get("LINUX_USB_DISTRO", request.target.distro))
        output = request.target.output_path.expanduser().resolve()
        return BuildPlan(request=request, env=env, output_path=output, provider=provider)

    def plan_from_namespace(self, args, *, output_path: str | Path | None = None) -> BuildPlan:
        return self.plan(build_request_from_namespace(args, output_path=output_path))

    def run_dry_run(self, plan: BuildPlan) -> int:
        return self._dry_run_runner(plan.env, self.runtime_root)

    def runner(self) -> ImageBuildRunner:
        if self._runner_factory is not None:
            return self._runner_factory()
        return ScriptImageBuildRunner(self.runtime_root, self.default_output_dir)

    def execute(self, plan: BuildPlan, log: BuildLog | None = None) -> BuildResult:
        return self.runner().run(plan.env, plan.output_path, log=log)


@dataclass(frozen=True)
class FlashPlan:
    image: Path
    device: str
    device_rows: list[tuple[str, str]]
    image_size_bytes: int


class FlashImageService:
    def plan(self, image: str | Path, device: str) -> FlashPlan:
        image_path = Path(image).expanduser().resolve()
        dev = selected_device(device)
        if not image_path.exists():
            raise ValueError(f"Image not found: {image_path}")
        if not dev:
            raise ValueError("Invalid target device.")
        image_check = validate_usb_image(image_path)
        if not image_check.ok:
            raise ValueError(image_check.reason or "Image failed validation.")
        ok_safe, safe_dev, device_rows, reason = device_safety_report(dev)
        if not ok_safe:
            raise ValueError(reason or "Unsafe target device.")
        return FlashPlan(
            image=image_path,
            device=safe_dev,
            device_rows=device_rows,
            image_size_bytes=image_path.stat().st_size,
        )

    def execute(self, plan: FlashPlan) -> int:
        sysname = platform.system()
        if sysname == "Darwin":
            raw = plan.device.replace("/dev/disk", "/dev/rdisk")
            cmd = ["sudo", "dd", f"if={plan.image}", f"of={raw}", "bs=16m", "status=progress"]
            subprocess.run(["diskutil", "unmountDisk", plan.device])
            code = subprocess.call(cmd)
            subprocess.run(["sync"])
            subprocess.run(["diskutil", "eject", plan.device])
            return code
        if sysname == "Linux":
            cmd = [
                "dd",
                f"if={plan.image}",
                f"of={plan.device}",
                "bs=16M",
                "iflag=fullblock",
                "status=progress",
                "conv=fsync",
            ]
            if os.geteuid() != 0:
                cmd.insert(0, shutil.which("pkexec") or "sudo")
            return subprocess.call(cmd)
        raise RuntimeError("Windows flashing is not implemented. Use Rufus/balenaEtcher with the generated image.")


class ListDevicesService:
    def list(self) -> list[tuple[str, str]]:
        return list_devices()


@dataclass(frozen=True)
class HostCheck:
    name: str
    ok: bool
    required: bool = True


class DoctorService:
    def checks(self) -> list[HostCheck]:
        sysname = platform.system()
        checks: list[HostCheck] = []
        if sysname == "Darwin":
            checks.append(HostCheck("docker", shutil.which("docker") is not None))
            if shutil.which("docker"):
                checks.append(
                    HostCheck(
                        "docker running",
                        subprocess.run(
                            ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
                        ).returncode
                        == 0,
                    )
                )
            checks.append(HostCheck("diskutil", shutil.which("diskutil") is not None))
        elif sysname == "Linux":
            for name in ["sudo", "python3", "mmd", "mcopy", "mdir", "grub-mkstandalone", "dd", "lsblk"]:
                checks.append(HostCheck(name, shutil.which(name) is not None))
            for optional in ["debootstrap", "pacstrap", "dnf", "zypper", "xbps-install", "nix"]:
                checks.append(HostCheck(f"optional {optional}", shutil.which(optional) is not None, required=False))
        else:
            checks.append(HostCheck("unsupported OS for flashing", False))
        return checks

    def failed(self, checks: list[HostCheck] | None = None) -> bool:
        return any(not check.ok and check.required for check in (checks if checks is not None else self.checks()))
