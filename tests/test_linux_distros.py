from __future__ import annotations

import pytest

from alpine_usb.linux_distros import gentoo
from alpine_usb.linux_distros.providers import get_provider


def test_get_provider_preserves_alpine_and_adds_gentoo() -> None:
    assert get_provider("alpine").default_branch == "latest-stable"
    assert get_provider("gentoo").default_branch == "stable"


@pytest.mark.parametrize("branch", ["stable", "testing"])
def test_gentoo_validate_branch_accepts_supported_channels(branch: str) -> None:
    assert gentoo.validate_branch(branch) == branch


@pytest.mark.parametrize("branch", ["", "latest-stable", "edge", "../stable"])
def test_gentoo_validate_branch_rejects_unsupported_channels(branch: str) -> None:
    with pytest.raises(ValueError):
        gentoo.validate_branch(branch)


@pytest.mark.parametrize("atom", ["www-client/firefox", "sys-kernel/gentoo-kernel-bin", "vim"])
def test_gentoo_validate_package_atom_accepts_safe_atoms(atom: str) -> None:
    assert gentoo.validate_package_atom(atom) == atom


@pytest.mark.parametrize("atom", ["", "-bad", "bad/name/extra", "bad atom", "$(bad)"])
def test_gentoo_validate_package_atom_rejects_unsafe_atoms(atom: str) -> None:
    with pytest.raises(ValueError):
        gentoo.validate_package_atom(atom)


def test_gentoo_search_uses_curated_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gentoo, "_local_search", lambda query, limit: [])

    results = gentoo.search_gentoo_packages("firefox", limit=5)

    assert results[0]["name"] in {"www-client/firefox", "www-client/firefox-bin"}


def test_gentoo_feature_package_atoms_maps_desktop_stack() -> None:
    atoms = gentoo.feature_package_atoms(
        {
            "desktop": "xfce",
            "display_manager": "lightdm",
            "browser": "firefox",
            "audio": "pipewire",
            "network": "networkmanager",
            "wifi": True,
            "bluetooth": False,
            "bootloader": "grub",
            "kernel": "lts",
            "firmware": "full",
            "legacy_x11_drivers": False,
            "auto_resize": True,
            "extra_packages": "app-misc/ranger",
        }
    )

    assert "xfce-base/xfce4-meta" in atoms
    assert "x11-misc/lightdm" in atoms
    assert "www-client/firefox-bin" in atoms
    assert "app-misc/ranger" in atoms
    assert "net-wireless/bluez" not in atoms
