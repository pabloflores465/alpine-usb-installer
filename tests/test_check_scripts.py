from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable() -> None:
    script = ROOT / "scripts" / "check-image-compile.sh"

    assert script.exists()
    assert os.access(script, os.X_OK)


def test_project_check_runs_image_compile_check_with_opt_out() -> None:
    project_check = (ROOT / "scripts" / "check-project.sh").read_text()

    assert "scripts/check-image-compile.sh" in project_check
    assert "SKIP_IMAGE_COMPILE_CHECK" in project_check
