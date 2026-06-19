from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_script_is_executable_and_checks_real_plans() -> None:
    script = ROOT / "scripts" / "check-image-compile.sh"
    text = script.read_text()

    assert os.access(script, os.X_OK)
    assert "python3 -m compileall alpine_usb" in text
    assert "./alpine-usb build" in text
    assert "--distro slackware" in text
    assert "Slackware USB configuration dry-run" in text
    assert "DRY RUN OK" in text
    assert "LINUX_USB_FULL_IMAGE_COMPILE" in text


def test_project_check_runs_image_compile_with_opt_out() -> None:
    text = (ROOT / "scripts" / "check-project.sh").read_text()

    assert "scripts/check-image-compile.sh" in text
    assert "SKIP_IMAGE_COMPILE_CHECK" in text
