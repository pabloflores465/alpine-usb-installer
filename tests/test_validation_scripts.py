from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_script_is_executable_and_checks_real_cli_artifacts() -> None:
    script = ROOT / "scripts" / "check-image-compile.sh"
    text = script.read_text(encoding="utf-8")

    assert script.exists()
    assert os.access(script, os.X_OK)
    assert "./alpine-usb build" in text
    assert "--distro arch" in text
    assert "Arch dry-run OK" in text
    assert "DRY RUN OK" in text
    assert "ARCH_USB_PACKAGES_FILE" in text
    assert "need_file_nonempty" in text


def test_project_check_runs_image_compile_with_opt_out() -> None:
    text = (ROOT / "scripts" / "check-project.sh").read_text(encoding="utf-8")

    assert "scripts/check-image-compile.sh" in text
    assert "SKIP_IMAGE_COMPILE_CHECK" in text


def test_readme_mentions_image_compile_check() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "scripts/check-image-compile.sh" in text
    assert "SKIP_IMAGE_COMPILE_CHECK=1" in text
