from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.void_packages.index import search_official_void_packages, validate_void_repository
from ledit_core.void_packages.index import validate_package_name as validate_void_package_name


def _search_void(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_void_packages(branch, arch, query, limit)


VOID_PROVIDER = DistroProvider(
    id="void",
    label="Void Linux (glibc)",
    package_manager="XBPS",
    default_branch="current",
    branch_label="Void repository",
    branch_help="current, glibc, or explicit repository URL",
    branch_choices=("current", "glibc"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="void",
    default_hostname="ledit-void",
    default_image_name="ledit-void.img",
    build_script="backend/scripts/build-void-usb.sh",
    configure_script="backend/scripts/configure-void-usb.sh",
    env_prefix="VOID_USB",
    script_env_prefix="LEDIT_USB",
    branch_env="VOID_REPOSITORY",
    search_repos=("current",),
    validate_branch_func=validate_void_repository,
    validate_package_func=validate_void_package_name,
    search_func=_search_void,
)
