from __future__ import annotations

from ledit_core.arch_packages.index import (
    ARCH_SEARCH_REPOS,
    search_official_arch_packages,
    validate_arch_branch,
    validate_arch_package_name,
)
from ledit_core.linux_distros.models import DistroProvider


def _search_arch(_branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_arch_packages(query, arch, limit)


ARCH_PROVIDER = DistroProvider(
    id="arch",
    label="Arch Linux",
    package_manager="Pacman",
    default_branch="rolling",
    branch_label="Arch branch",
    branch_help="rolling (stable is accepted as an alias)",
    branch_choices=("rolling", "stable"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="arch",
    default_hostname="ledit-arch",
    default_image_name="ledit-arch.img",
    build_script="ledit_core/backend/scripts/build-arch-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-arch-usb.sh",
    env_prefix="ARCH_USB",
    script_env_prefix="LEDIT_USB",
    branch_env="ARCH_USB_BRANCH",
    search_repos=ARCH_SEARCH_REPOS,
    validate_branch_func=validate_arch_branch,
    validate_package_func=validate_arch_package_name,
    search_func=_search_arch,
)
