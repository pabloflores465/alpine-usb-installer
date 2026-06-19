from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable_and_integrated() -> None:
    script = PROJECT_ROOT / "scripts" / "check-image-compile.sh"
    check_project = PROJECT_ROOT / "scripts" / "check-project.sh"

    assert script.is_file()
    assert os.access(script, os.X_OK)

    check_project_text = check_project.read_text()
    assert "scripts/check-image-compile.sh" in check_project_text
    assert "SKIP_IMAGE_COMPILE_CHECK" in check_project_text
