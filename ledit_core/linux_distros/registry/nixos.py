from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.nixos.packages import (
    NIXOS_DEFAULT_CHANNEL,
    NIXOS_STABLE_CHANNELS,
    search_nix_packages,
    validate_nix_channel,
    validate_nix_package_name,
)


def _search_nixos(branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_nix_packages(branch, query, limit)


NIXOS_PROVIDER = DistroProvider(
    id="nixos",
    label="NixOS",
    package_manager="nixpkgs",
    default_branch=NIXOS_DEFAULT_CHANNEL,
    branch_label="NixOS channel",
    branch_help=", ".join(NIXOS_STABLE_CHANNELS),
    branch_choices=tuple(NIXOS_STABLE_CHANNELS),
    default_arch="x86_64-linux",
    arch_choices=("x86_64-linux", "x86_64"),
    default_user="nixos",
    default_hostname="ledit-nixos",
    default_image_name="ledit-nixos.img",
    build_script=None,
    configure_script=None,
    env_prefix="NIXOS_USB",
    branch_env="NIXOS_CHANNEL",
    search_repos=("nixpkgs",),
    validate_branch_func=validate_nix_channel,
    validate_package_func=validate_nix_package_name,
    search_func=_search_nixos,
    supports_dry_run_script=False,
    supports_gui_build_worker=False,
    supports_systemd_boot=False,
    supports_extlinux=True,
)
