from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable() -> None:
    script = ROOT / "scripts" / "check-image-compile.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_project_check_runs_image_compile_check_with_opt_out() -> None:
    check_project = (ROOT / "scripts" / "check-project.sh").read_text()

    assert "SKIP_IMAGE_COMPILE_CHECK" in check_project
    assert "scripts/check-image-compile.sh" in check_project
