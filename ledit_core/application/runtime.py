from __future__ import annotations

import sys
from pathlib import Path

from ledit_core.image_builds import runtime as build_runtime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
TERMINAL_RUNTIME_RESOURCES = build_runtime.RUNTIME_RESOURCES

_TERMINAL_RUNTIME_DIR: Path | None = None


def can_write_to_dir(path: Path) -> bool:
    return build_runtime.can_write_to_dir(path)


def secure_runtime_dir(name: str) -> Path:
    return build_runtime.secure_runtime_dir(name)


def prepare_terminal_runtime(source_dir: Path) -> Path:
    return build_runtime.prepare_runtime(
        source_dir,
        "terminal-runtime",
        TERMINAL_RUNTIME_RESOURCES,
        secure_dir=secure_runtime_dir,
    )


def terminal_runtime_root(source_dir: Path = SOURCE_DIR) -> Path:
    global _TERMINAL_RUNTIME_DIR
    if _TERMINAL_RUNTIME_DIR is not None:
        return _TERMINAL_RUNTIME_DIR
    if getattr(sys, "frozen", False):
        _TERMINAL_RUNTIME_DIR = prepare_terminal_runtime(source_dir)
        return _TERMINAL_RUNTIME_DIR
    if can_write_to_dir(source_dir):
        return source_dir
    _TERMINAL_RUNTIME_DIR = prepare_terminal_runtime(source_dir)
    return _TERMINAL_RUNTIME_DIR
