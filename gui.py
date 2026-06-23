#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _qt_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".qtvenv" / "Scripts" / "python.exe"
    return root / ".qtvenv" / "bin" / "python"


def _install_qt_deps(root: Path, python: Path) -> None:
    requirements = root / "requirements.txt"
    if requirements.exists():
        subprocess.check_call(
            [
                str(python),
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
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "PySide6_Essentials"]
        )


def _has_pyside6(python: Path) -> bool:
    return (
        subprocess.run(
            [str(python), "-c", "import PySide6"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _bootstrap_qt_venv() -> None:
    root = Path(__file__).resolve().parent
    python = _qt_python(root)
    if Path(sys.executable).resolve() == python.resolve():
        return
    if not python.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(root / ".qtvenv")])
    if not _has_pyside6(python):
        _install_qt_deps(root, python)
    os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])


_bootstrap_qt_venv()

from ledit_core.interfaces.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
