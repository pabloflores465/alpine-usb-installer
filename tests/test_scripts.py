from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_image_compile_check_script_is_executable():
    script = REPO_ROOT / "scripts" / "check-image-compile.sh"

    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_project_check_runs_image_compile_check_with_opt_out():
    project_check = (REPO_ROOT / "scripts" / "check-project.sh").read_text()

    assert "SKIP_IMAGE_COMPILE_CHECK" in project_check
    assert "scripts/check-image-compile.sh" in project_check
