from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable_and_checks_real_cli_dry_runs() -> None:
    script = REPO_ROOT / "scripts" / "check-image-compile.sh"

    assert script.exists()
    assert os.access(script, os.X_OK)
    text = script.read_text()
    assert "./alpine-usb build" in text
    assert "--distro opensuse" in text
    assert 'WORK_DIR=".work/image-compile"' in text
    assert "opensuse.log" in text
    assert "alpine.log" in text
    assert "openSUSE USB configuration plan" in text
    assert "DRY RUN OK" in text


def test_project_check_runs_image_compile_check_with_opt_out() -> None:
    text = (REPO_ROOT / "scripts" / "check-project.sh").read_text()

    assert "SKIP_IMAGE_COMPILE_CHECK" in text
    assert "scripts/check-image-compile.sh" in text
