from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ledit_core.image_builds.secrets import cleanup_secret_files, prepare_secret_env
from ledit_core.linux_distros import get_distro
from ledit_core.nixos.build import env_to_config as nixos_env_to_config
from ledit_core.nixos.build import run_nixos_dry_run


def run_config_dry_run(env: dict[str, str], repo_root: Path) -> int:
    provider = get_distro(env.get("LINUX_USB_DISTRO", "alpine"))
    if provider.id == "nixos":
        return run_nixos_dry_run(nixos_env_to_config(env))
    dry_env = os.environ.copy()
    safe_env, secret_files = prepare_secret_env(env, repo_root)
    dry_env.update(safe_env)
    dry_env.pop("IMAGE_NAME", None)
    dry_env[f"{provider.script_prefix}_DRY_RUN"] = "1"
    dry_env[f"{provider.env_prefix}_DRY_RUN"] = "1"
    try:
        if provider.configure_script:
            script = provider.configure_script_path(repo_root)
            assert script is not None
            script.chmod(0o755)
            proc = subprocess.Popen([f"./{script.name}"], cwd=repo_root, env=dry_env)
        else:
            script = provider.build_script_path(repo_root)
            if script is None:
                raise RuntimeError(f"No dry-run adapter configured for {provider.label}")
            script.chmod(0o755)
            proc = subprocess.Popen([f"./{script.name}", "--dry-run"], cwd=repo_root, env=dry_env)
        return proc.wait()
    finally:
        cleanup_secret_files(secret_files)
