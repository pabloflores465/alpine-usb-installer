from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable_and_integrated() -> None:
    script = ROOT / "scripts" / "check-image-compile.sh"
    check_project = ROOT / "scripts" / "check-project.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111
    text = check_project.read_text()
    assert "scripts/check-image-compile.sh" in text
    assert "SKIP_IMAGE_COMPILE_CHECK" in text
