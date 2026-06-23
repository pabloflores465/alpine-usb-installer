from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

from ledit_core.linux_distros import DISTROS

BUILD_SCRIPT_RESOURCES = tuple(
    sorted(
        {
            script
            for provider in DISTROS.values()
            for script in (provider.build_script, provider.configure_script)
            if script
        }
    )
)

RUNTIME_RESOURCES = (
    *BUILD_SCRIPT_RESOURCES,
    "README.md",
    "LICENSE",
    "efi-fallback",
    "backend/docker/Dockerfile.builder",
    "backend/docker/Dockerfile.gentoo-builder",
)


def can_write_to_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write-test-{os.getpid()}"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def secure_runtime_dir(name: str, *, app_name: str = "ledit") -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    base = Path(tempfile.gettempdir()) / f"{app_name}-{uid}"
    for path in [base, base / name]:
        if path.is_symlink():
            raise RuntimeError(f"Refusing symlinked runtime path: {path}")
        if path.exists():
            st = path.stat()
            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                raise RuntimeError(f"Refusing runtime path not owned by current user: {path}")
            if stat.S_IMODE(st.st_mode) & 0o077:
                path.chmod(0o700)
        else:
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    return base / name


def prepare_runtime(
    source_dir: Path,
    runtime_name: str,
    resources: tuple[str, ...] = RUNTIME_RESOURCES,
    *,
    secure_dir: Callable[[str], Path] = secure_runtime_dir,
) -> Path:
    runtime = secure_dir(runtime_name)
    for name in resources:
        src = source_dir / name
        dst = runtime / name
        if not src.exists():
            continue
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if name.endswith(".sh"):
                dst.chmod(0o755)
    (runtime / ".work").mkdir(exist_ok=True)
    (runtime / ".work").chmod(0o700)
    return runtime
