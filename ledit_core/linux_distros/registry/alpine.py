from __future__ import annotations

from ledit_core.apk_packages.index import APK_SEARCH_REPOS, search_official_apk_packages
from ledit_core.apk_packages.index import validate_branch as validate_apk_branch
from ledit_core.apk_packages.index import validate_package_name as validate_apk_package_name
from ledit_core.linux_distros.models import DistroProvider


def _search_alpine(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_apk_packages(branch, arch, query, limit)


ALPINE_PROVIDER = DistroProvider(
    id="alpine",
    label="Alpine Linux",
    package_manager="APK",
    default_branch="latest-stable",
    branch_label="Alpine branch",
    branch_help="latest-stable, edge, v3.22, ...",
    branch_choices=("latest-stable", "edge", "v3.22", "v3.21"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="alpine",
    default_hostname="ledit-linux",
    default_image_name="ledit.img",
    build_script="backend/scripts/build-alpine-usb.sh",
    configure_script="backend/scripts/configure-alpine-usb.sh",
    env_prefix="LEDIT_USB",
    branch_env="ALPINE_BRANCH",
    search_repos=APK_SEARCH_REPOS,
    validate_branch_func=validate_apk_branch,
    validate_package_func=validate_apk_package_name,
    search_func=_search_alpine,
)
