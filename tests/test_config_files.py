from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from alpine_usb.build_profiles.config_files import (
    ConfigFileError,
    load_config_file,
    parse_config,
    save_config_file,
    scrub_config,
)

SAMPLE_CONFIG = {
    "image": "/tmp/alpine.img",
    "image_size": "32G",
    "hostname": "alpine-laptop",
    "wifi": True,
    "bluetooth": False,
    "wms": ["i3", "sway"],
    "extra_packages": "htop vim",
    "password": "secret",
    "root_password": "root-secret",
}


def test_scrub_config_removes_password_fields() -> None:
    scrubbed = scrub_config(SAMPLE_CONFIG)

    assert "password" not in scrubbed
    assert "root_password" not in scrubbed
    assert scrubbed["hostname"] == "alpine-laptop"


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".yml"])
def test_save_and_load_config_file_without_passwords(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"profile{suffix}"

    save_config_file(path, SAMPLE_CONFIG)
    loaded = load_config_file(path)

    assert loaded["image_size"] == "32G"
    assert loaded["wifi"] is True
    assert loaded["bluetooth"] is False
    assert loaded["wms"] == ["i3", "sway"]
    assert "password" not in loaded
    assert "root_password" not in loaded


def test_parse_yaml_accepts_simple_mapping_and_lists() -> None:
    loaded = parse_config(
        dedent(
            """
            image_size: "64G"
            wifi: true
            bluetooth: false
            wms:
              - "hyprland"
              - "labwc"
            extra_packages: "firefox htop"
            password: "do-not-load"
            """
        ),
        "yaml",
    )

    assert loaded == {
        "image_size": "64G",
        "wifi": True,
        "bluetooth": False,
        "wms": ["hyprland", "labwc"],
        "extra_packages": "firefox htop",
    }


def test_parse_rejects_non_mapping_json() -> None:
    with pytest.raises(ConfigFileError, match="object/mapping"):
        parse_config("[]", "json")


def test_load_rejects_unknown_suffix(tmp_path: Path) -> None:
    path = tmp_path / "profile.toml"
    path.write_text("image_size = '16G'")

    with pytest.raises(ConfigFileError, match="Unsupported configuration format"):
        load_config_file(path)
