# ruff: noqa: E402
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# This module can be executed directly after the dev GUI bootstrap re-execs into
# .qtvenv. In that path, sys.path[0] is ledit_core/interfaces, so add project
# root before importing sibling screaming-architecture packages.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ledit_core.image_builds import BUILD_SCRIPT_RESOURCES
from ledit_core.image_builds.runtime import prepare_runtime, secure_runtime_dir


def prepare_frozen_runtime(bundle_dir: Path) -> Path:
    """Copy bundled build resources to a writable, stable directory."""
    return prepare_runtime(
        bundle_dir,
        "app-runtime",
        (
            *BUILD_SCRIPT_RESOURCES,
            "README.md",
            "LICENSE",
            "ledit_core/backend/efi-fallback",
            "ledit_core/backend/docker/Dockerfile.builder",
            "ledit_core/backend/docker/Dockerfile.gentoo-builder",
        ),
        secure_dir=secure_runtime_dir,
    )


if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    SCRIPT_DIR = prepare_frozen_runtime(BUNDLE_DIR)
else:
    SCRIPT_DIR = PROJECT_ROOT
    QT_VENV_PYTHON = SCRIPT_DIR / ".qtvenv" / "bin" / "python"
    if Path(sys.executable).parent.resolve() != QT_VENV_PYTHON.parent.resolve():
        if not QT_VENV_PYTHON.exists():
            subprocess.check_call([sys.executable, "-m", "venv", str(SCRIPT_DIR / ".qtvenv")])
            requirements = SCRIPT_DIR / "requirements.txt"
            if requirements.exists():
                subprocess.check_call(
                    [
                        str(QT_VENV_PYTHON),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "-r",
                        str(requirements),
                    ]
                )
            else:
                subprocess.check_call(
                    [str(QT_VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "PySide6_Essentials"]
                )
        gui_app = Path(__file__).resolve().with_name("app.py")
        os.execv(str(QT_VENV_PYTHON), [str(QT_VENV_PYTHON), str(gui_app), *sys.argv[1:]])
os.chdir(SCRIPT_DIR)

# Finder-launched macOS apps get a minimal PATH. Add common CLI locations so
# Docker Desktop and Nix/Homebrew tools are discoverable from the standalone app.
HOST_PATHS = [
    "/run/current-system/sw/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/Applications/Docker.app/Contents/Resources/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
]
os.environ["PATH"] = os.pathsep.join([p for p in HOST_PATHS if Path(p).exists()] + [os.environ.get("PATH", "")])
