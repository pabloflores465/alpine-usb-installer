from __future__ import annotations

import argparse

from ledit_core.build_profiles import presets


def build_args(**overrides) -> argparse.Namespace:
    values = {
        "command": "build",
        "profile": "minimal",
        "desktop": "xfce",
        "display_manager": "auto",
        "browser": "firefox",
        "audio": "pipewire",
        "network": "networkmanager",
        "wifi": True,
        "bluetooth": True,
        "firmware": "full",
        "legacy_x11_drivers": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_apply_minimal_profile_defaults_when_options_not_explicit() -> None:
    args = build_args()

    presets.apply_profile_defaults(args, ["build", "--profile", "minimal"])

    assert args.desktop == "none"
    assert args.display_manager == "none"
    assert args.browser == "none"
    assert args.audio == "none"
    assert args.network == "none"
    assert args.wifi is False
    assert args.bluetooth is False
    assert args.firmware == "none"
    assert args.legacy_x11_drivers is False


def test_apply_minimal_profile_preserves_explicit_overrides() -> None:
    args = build_args()

    presets.apply_profile_defaults(args, ["build", "--profile=minimal", "--desktop", "xfce", "--wifi"])

    assert args.desktop == "xfce"
    assert args.wifi is True
    assert args.bluetooth is False


def test_non_build_command_does_not_apply_profile_defaults() -> None:
    args = build_args(command="search")

    presets.apply_profile_defaults(args, ["search", "firefox"])

    assert args.desktop == "xfce"
