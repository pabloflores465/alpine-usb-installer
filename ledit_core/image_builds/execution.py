from __future__ import annotations

import contextlib
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ledit_core.image_builds.secrets import cleanup_secret_files, prepare_secret_env
from ledit_core.linux_distros import get_distro
from ledit_core.nixos.build import env_to_config as nixos_env_to_config
from ledit_core.nixos.build import run_nixos_build

BuildLog = Callable[[str], None]

DOCKER_NAME_ENV_KEYS = (
    "LEDIT_USB_DOCKER_NAME",
    "ARCH_USB_DOCKER_NAME",
    "DEBIAN_USB_DOCKER_NAME",
    "FEDORA_USB_DOCKER_NAME",
    "GENTOO_USB_DOCKER_NAME",
    "NIXOS_USB_DOCKER_NAME",
    "OPENSUSE_USB_DOCKER_NAME",
    "RHEL_USB_DOCKER_NAME",
    "SLACKWARE_USB_DOCKER_NAME",
    "UBUNTU_USB_DOCKER_NAME",
    "VOID_USB_DOCKER_NAME",
)


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    message: str
    code: int = 0


class ImageBuildRunner(Protocol):
    def run(self, config_env: dict[str, str], output_path: str | Path, log: BuildLog | None = None) -> BuildResult: ...

    def cancel(self, log: BuildLog | None = None) -> None: ...

    def force_cancel(self, log: BuildLog | None = None) -> None: ...


def _emit(log: BuildLog | None, message: str) -> None:
    if not log:
        return
    with contextlib.suppress(RuntimeError):
        log(message)


def _remove_cleanup_path(path: Path, log: BuildLog | None) -> None:
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
            _emit(log, f"Removed build workspace: {path}")
        elif path.exists() or path.is_symlink():
            path.unlink()
            _emit(log, f"Removed partial image: {path}")
    except FileNotFoundError:
        pass
    except OSError as exc:
        _emit(log, f"Could not remove build artifact {path}: {exc}")


def release_deleted_build_file_holders(roots: list[Path], log: BuildLog | None) -> None:
    if platform.system() != "Darwin":
        return
    lsof = shutil.which("lsof")
    if not lsof:
        return
    try:
        proc = subprocess.run([lsof, "+L1"], text=True, capture_output=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return
    root_text = [str(root.expanduser()) for root in roots if root]
    pids: set[int] = set()
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        try:
            pid = int(parts[1])
            size = int(parts[6])
        except ValueError:
            continue
        if pid == os.getpid() or size < 100 * 1024 * 1024:
            continue
        name = parts[8]
        if not any(name.startswith(root) for root in root_text):
            continue
        if not any(token in name for token in (".img", ".raw", ".zst", "/.work/", "ledit")):
            continue
        pids.add(pid)
    for pid in sorted(pids):
        _emit(log, f"Stopping process {pid} still holding deleted build image data...")
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGTERM)
    if pids:
        time.sleep(1)
    for pid in sorted(pids):
        try:
            os.kill(pid, 0)
        except OSError:
            continue
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)


def cleanup_build_artifacts(
    output_path: str | Path,
    image_name: str,
    runtime_root: Path,
    default_output_dir: Path,
    log: BuildLog | None = None,
) -> None:
    output = Path(output_path).expanduser()
    candidates = {
        output,
        Path(str(output) + ".tmp"),
        runtime_root / image_name,
        runtime_root / f"{image_name}.tmp",
        default_output_dir / image_name,
        default_output_dir / f"{image_name}.tmp",
    }
    for pattern in ("*.img.tmp", "*.raw.tmp", "*.img", "*.raw"):
        candidates.update(runtime_root.glob(pattern))
    for candidate in sorted(candidates, key=lambda item: str(item)):
        _remove_cleanup_path(candidate, log)
    _remove_cleanup_path(runtime_root / ".work", log)
    release_deleted_build_file_holders(
        [runtime_root, output.parent, default_output_dir, Path(tempfile.gettempdir()) / "ledit"],
        log,
    )


class ScriptImageBuildRunner:
    def __init__(self, runtime_root: Path, default_output_dir: Path, docker_container_name: str | None = None):
        self.runtime_root = runtime_root
        self.default_output_dir = default_output_dir
        self.proc: subprocess.Popen | None = None
        self.cancel_requested = False
        self.docker_container_name = docker_container_name or f"ledit-build-{os.getpid()}-{int(time.time() * 1000)}"

    def stop_docker_container(self) -> None:
        docker = shutil.which("docker")
        if not docker:
            return
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                [docker, "rm", "-f", self.docker_container_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )

    def stop_process_group(self, sig: signal.Signals) -> None:
        proc = self.proc
        if not proc or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except OSError:
            if sig == signal.SIGTERM:
                proc.terminate()
            else:
                proc.kill()

    def force_cancel(self, log: BuildLog | None = None) -> None:
        if not self.cancel_requested or not self.thread_running_self():
            return
        _emit(log, "Build did not stop after SIGTERM; forcing cleanup...")
        self.stop_docker_container()
        self.stop_process_group(signal.SIGKILL)

    def thread_running_self(self) -> bool:
        proc = self.proc
        return bool(proc and proc.poll() is None)

    def cancel(self, log: BuildLog | None = None) -> None:
        self.cancel_requested = True
        _emit(log, "Stopping build process...")
        self.stop_docker_container()
        self.stop_process_group(signal.SIGTERM)

    def cleanup_partial_output(self, output_path: str | Path, image_name: str, log: BuildLog | None = None) -> None:
        cleanup_build_artifacts(output_path, image_name, self.runtime_root, self.default_output_dir, log)

    def run(self, config_env: dict[str, str], output_path: str | Path, log: BuildLog | None = None) -> BuildResult:
        secret_files: list[Path] = []
        try:
            distro_id = str(config_env.get("LINUX_USB_DISTRO", "alpine"))
            provider = get_distro(distro_id)
            final = str(Path(output_path).expanduser().resolve())
            Path(final).parent.mkdir(parents=True, exist_ok=True)
            if os.path.exists(final):
                os.remove(final)
            if provider.id == "nixos":
                code = run_nixos_build(
                    nixos_env_to_config({k: str(v) for k, v in config_env.items()}), Path(final), log=log
                )
                if self.cancel_requested:
                    self.cleanup_partial_output(
                        final, str(config_env.get("IMAGE_NAME", provider.default_image_name)), log
                    )
                    return BuildResult(False, "Build stopped and partial image cleaned.", code)
                if code != 0:
                    raise RuntimeError(f"Build failed with exit code {code}")
                return BuildResult(True, f"Image build complete: {final}")
            env = os.environ.copy()
            safe_config_env, secret_files = prepare_secret_env(
                {k: str(v) for k, v in config_env.items()}, self.runtime_root
            )
            env.update(safe_config_env)
            env.setdefault("IMAGE_NAME", provider.default_image_name)
            for docker_name_var in DOCKER_NAME_ENV_KEYS:
                env[docker_name_var] = self.docker_container_name
            env["OUTPUT_PATH"] = final
            script = self.runtime_root / str(provider.build_script)
            if not script.exists():
                raise RuntimeError(f"Build script not found: {script}")
            script.chmod(0o755)
            configure = self.runtime_root / str(provider.configure_script) if provider.configure_script else None
            if configure and configure.exists():
                configure.chmod(0o755)
            self.proc = subprocess.Popen(
                [str(script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=str(self.runtime_root),
                start_new_session=True,
            )
            for line in self.proc.stdout or []:
                _emit(log, line.rstrip())
            code = self.proc.wait()
            if self.cancel_requested:
                self.cleanup_partial_output(final, str(config_env.get("IMAGE_NAME", provider.default_image_name)), log)
                return BuildResult(False, "Build stopped and partial image cleaned.", code)
            if code != 0:
                raise RuntimeError(f"Build failed with exit code {code}")
            if not os.path.exists(final):
                raise RuntimeError(f"Build finished but expected image was not found: {final}")
            return BuildResult(True, f"Image build complete: {final}")
        except Exception as exc:
            self.cleanup_partial_output(output_path, str(config_env.get("IMAGE_NAME", "ledit.img")), log)
            return BuildResult(False, str(exc), 1)
        finally:
            self.proc = None
            cleanup_secret_files(secret_files)
