from __future__ import annotations

import contextlib
import os
from pathlib import Path

from ledit_core.linux_distros import DISTROS


def secret_env_to_file() -> dict[str, str]:
    prefixes = {provider.script_prefix for provider in DISTROS.values()} | {
        provider.env_prefix for provider in DISTROS.values()
    }
    return {
        **{f"{prefix}_PASSWORD": f"{prefix}_PASSWORD_FILE" for prefix in prefixes},
        **{f"{prefix}_ROOT_PASSWORD": f"{prefix}_ROOT_PASSWORD_FILE" for prefix in prefixes},
    }


SECRET_ENV_TO_FILE = secret_env_to_file()


def prepare_secret_env(env: dict[str, str], secret_root: Path) -> tuple[dict[str, str], list[Path]]:
    safe_env = dict(env)
    created: list[Path] = []
    secret_dir = secret_root / ".work" / "secrets"
    secret_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.chmod(0o700)
    for key, file_key in SECRET_ENV_TO_FILE.items():
        if key not in safe_env:
            continue
        value = safe_env.pop(key, "")
        path = secret_dir / f"{key.lower()}-{os.getpid()}.secret"
        path.write_text(value)
        path.chmod(0o600)
        safe_env[file_key] = str(path)
        created.append(path)
    return safe_env, created


def cleanup_secret_files(paths: list[Path]) -> None:
    for path in paths:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
