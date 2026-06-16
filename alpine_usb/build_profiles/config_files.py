from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PASSWORD_KEYS = frozenset({"password", "root_password", "ALPINE_USB_PASSWORD", "ALPINE_USB_ROOT_PASSWORD"})
YAML_SUFFIXES = frozenset({".yaml", ".yml"})
JSON_SUFFIXES = frozenset({".json"})


class ConfigFileError(ValueError):
    """Raised when an image configuration file cannot be parsed or written."""


def scrub_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with any password-like keys removed."""
    return {key: value for key, value in config.items() if key not in PASSWORD_KEYS}


def config_format_for_path(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in YAML_SUFFIXES:
        return "yaml"
    if suffix in JSON_SUFFIXES or not suffix:
        return "json"
    raise ConfigFileError(f"Unsupported configuration format: {suffix}. Use .json, .yaml, or .yml")


def serialize_config(config: dict[str, Any], fmt: str) -> str:
    clean = scrub_config(config)
    if fmt == "json":
        return json.dumps(clean, indent=2, sort_keys=True) + "\n"
    if fmt == "yaml":
        return _dump_simple_yaml(clean)
    raise ConfigFileError(f"Unsupported configuration format: {fmt}")


def parse_config(text: str, fmt: str) -> dict[str, Any]:
    try:
        if fmt == "json":
            parsed = json.loads(text)
        elif fmt == "yaml":
            parsed = _parse_simple_yaml(text)
        else:
            raise ConfigFileError(f"Unsupported configuration format: {fmt}")
    except json.JSONDecodeError as exc:
        raise ConfigFileError(f"Invalid JSON configuration: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ConfigFileError("Configuration file must contain an object/mapping")
    return scrub_config(parsed)


def load_config_file(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser()
    try:
        text = config_path.read_text()
    except OSError as exc:
        raise ConfigFileError(f"Could not read configuration: {exc}") from exc
    return parse_config(text, config_format_for_path(config_path))


def save_config_file(path: str | Path, config: dict[str, Any]) -> None:
    config_path = Path(path).expanduser()
    fmt = config_format_for_path(config_path)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(serialize_config(config, fmt))
        config_path.chmod(0o600)
    except OSError as exc:
        raise ConfigFileError(f"Could not write configuration: {exc}") from exc


def _dump_simple_yaml(config: dict[str, Any]) -> str:
    lines = [
        "# Alpine USB Installer image configuration",
        "# Passwords are intentionally not saved.",
    ]
    for key, value in config.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {_yaml_scalar(value)}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return json.dumps(str(value))


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_list_key: str | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            if current_list_key is None or not stripped.startswith("- "):
                raise ConfigFileError(f"Invalid YAML list item on line {line_number}")
            result[current_list_key].append(_parse_yaml_scalar(stripped[2:].strip()))
            continue
        current_list_key = None
        if ":" not in line:
            raise ConfigFileError(f"Invalid YAML mapping on line {line_number}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ConfigFileError(f"Invalid YAML key on line {line_number}")
        if value == "":
            result[key] = []
            current_list_key = key
        else:
            result[key] = _parse_yaml_scalar(value)
    return result


def _parse_yaml_scalar(value: str) -> Any:
    if not value:
        return ""
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "~"}:
        return None
    if value.startswith(("'", '"', "[", "{")):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ConfigFileError(f"Invalid YAML scalar: {value}") from exc
    return value
