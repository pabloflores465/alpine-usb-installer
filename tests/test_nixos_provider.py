from __future__ import annotations

import argparse
import json
import subprocess

import pytest

from alpine_usb.nixos.config import config_from_args, generate_configuration_nix, generate_flake_nix
from alpine_usb.nixos.packages import search_nix_packages, validate_nix_package_name


def args(**overrides) -> argparse.Namespace:
    values = {
        "nixos_channel": "nixos-24.11",
        "branch": "latest-stable",
        "arch": "x86_64",
        "hostname": "nixos-usb",
        "user": "nixos",
        "password": "secret",
        "root_password": None,
        "timezone": "UTC",
        "locale": "en_US.UTF-8",
        "console_keymap": "us",
        "xkb_layout": "us",
        "xkb_variant": "",
        "xkb_model": "pc105",
        "desktop": "plasma",
        "display_manager": "auto",
        "default_session": "auto",
        "wm": ["sway", "sway"],
        "tiling_wms": "i3 openbox",
        "browser": "firefox",
        "audio": "pipewire",
        "network": "networkmanager",
        "wifi": True,
        "bluetooth": False,
        "bootloader": "systemd-boot",
        "kernel": "lts",
        "firmware": "full",
        "auto_resize": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_nixos_config_from_args_maps_common_usb_options() -> None:
    cfg = config_from_args(args(), "vim git")

    assert cfg.channel == "nixos-24.11"
    assert cfg.arch == "x86_64-linux"
    assert cfg.root_password == "secret"
    assert cfg.window_managers == ("sway", "i3", "openbox")
    assert cfg.extra_packages == ("vim", "git")


def test_generate_configuration_nix_contains_desktop_boot_network_and_packages() -> None:
    cfg = config_from_args(args(), "vim")
    text = generate_configuration_nix(cfg)

    assert "services.desktopManager.plasma6.enable = true;" in text
    assert "services.displayManager.sddm.enable = true;" in text
    assert "boot.loader.systemd-boot.enable = lib.mkForce true;" in text
    assert "networking.networkmanager.enable = true;" in text
    assert "boot.growPartition = true;" in text
    assert "pkgs.vim" in text
    assert "services.pipewire = { enable = true; alsa.enable = true; pulse.enable = true; };" in text
    assert "services.pulseaudio" not in text
    assert "sound.enable" not in text
    assert "pkgs.firefox" in text
    assert "pkgs.sway" in text


def test_generate_flake_pins_selected_channel() -> None:
    cfg = config_from_args(args(nixos_channel="nixos-25.05"), "")

    assert "github:NixOS/nixpkgs/nixos-25.05" in generate_flake_nix(cfg)


def test_validate_nix_package_name_rejects_path_injection() -> None:
    with pytest.raises(ValueError, match="Invalid Nix package"):
        validate_nix_package_name("../bad")


def test_search_nix_packages_uses_cache_and_normalises(tmp_path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "nix-search-nixos-24.11-firefox.json").write_text(
        json.dumps(
            {
                "legacyPackages.x86_64-linux.firefox": {
                    "pname": "firefox",
                    "version": "1",
                    "description": "browser",
                }
            }
        )
    )

    assert search_nix_packages("nixos-24.11", "firefox", cache_dir=cache) == [
        {"name": "firefox", "package": "firefox", "version": "1", "description": "browser", "repo": "nixpkgs"}
    ]


def test_search_nix_packages_shells_out_and_writes_cache(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["nix"],
            returncode=0,
            stdout=json.dumps({"legacyPackages.x86_64-linux.htop": {"version": "3", "description": "viewer"}}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    results = search_nix_packages("nixos-24.11", "htop", cache_dir=tmp_path)

    assert results[0]["name"] == "htop"
    assert (tmp_path / "nix-search-nixos-24.11-htop.json").exists()
