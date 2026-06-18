from __future__ import annotations

import pytest

from alpine_usb.rhel_packages.packages import normalize_rhel_distro, resolve_rhel_packages, validate_rhel_release


def test_normalize_rhel_distro_aliases() -> None:
    assert normalize_rhel_distro("rhel") == "rocky"
    assert normalize_rhel_distro("AlmaLinux") == "alma"
    assert normalize_rhel_distro("centos") == "centos-stream"


def test_validate_rhel_release_rejects_invalid_text() -> None:
    with pytest.raises(ValueError, match="RHEL-family release"):
        validate_rhel_release("rawhide/bad")


def test_resolve_rhel_packages_maps_desktop_services_and_extras() -> None:
    packages = resolve_rhel_packages(
        desktop="xfce",
        display_manager="auto",
        wms=["i3"],
        network="networkmanager",
        wifi=True,
        bluetooth=True,
        audio="pipewire",
        browser="firefox",
        firmware="full",
        auto_resize=True,
        extra_packages="vim-enhanced htop",
    )

    assert "@core" in packages
    assert "@xfce-desktop-environment" in packages
    assert "i3" in packages
    assert "NetworkManager-wifi" in packages
    assert "bluez" in packages
    assert "pipewire" in packages
    assert "firefox" in packages
    assert "linux-firmware" in packages
    assert "vim-enhanced" in packages


def test_resolve_rhel_packages_rejects_unmapped_window_manager() -> None:
    with pytest.raises(ValueError, match="not mapped"):
        resolve_rhel_packages(
            desktop="none",
            display_manager="none",
            wms=["hyprland"],
            network="none",
            wifi=False,
            bluetooth=False,
            audio="none",
            browser="none",
            firmware="none",
            auto_resize=False,
            extra_packages="",
        )
