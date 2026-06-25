from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.linux_distros.opensuse import (
    OPENSUSE_SEARCH_REPOS,
    search_official_opensuse_packages,
    validate_opensuse_release,
)
from ledit_core.linux_distros.opensuse import validate_package_name as validate_opensuse_package_name


def _search_opensuse(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_opensuse_packages(branch, arch, query, limit)


OPENSUSE_PROVIDER = DistroProvider(
    id="opensuse",
    label="openSUSE",
    package_manager="Zypper",
    default_branch="tumbleweed",
    branch_label="openSUSE release",
    branch_help="tumbleweed, leap-16.0, leap-15.6",
    branch_choices=("tumbleweed", "leap-16.0", "leap-15.6"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="linux",
    default_hostname="ledit-opensuse",
    default_image_name="ledit-opensuse.img",
    build_script="ledit_core/backend/scripts/build-opensuse-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-opensuse-usb.sh",
    env_prefix="OPENSUSE_USB",
    branch_env="OPENSUSE_RELEASE",
    search_repos=OPENSUSE_SEARCH_REPOS,
    validate_branch_func=validate_opensuse_release,
    validate_package_func=validate_opensuse_package_name,
    search_func=_search_opensuse,
)
