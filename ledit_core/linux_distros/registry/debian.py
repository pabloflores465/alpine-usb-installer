from __future__ import annotations

from ledit_core.deb_packages.index import DEBIAN_SEARCH_REPOS, search_official_deb_packages
from ledit_core.deb_packages.index import validate_package_name as validate_deb_package_name
from ledit_core.deb_packages.index import validate_release as validate_debian_release
from ledit_core.linux_distros.models import DistroProvider


def _search_debian(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_deb_packages(branch, arch, query, limit)


DEBIAN_PROVIDER = DistroProvider(
    id="debian",
    label="Debian",
    package_manager="APT",
    default_branch="stable",
    branch_label="Debian release",
    branch_help="stable, testing, sid, bookworm, trixie, forky",
    branch_choices=("stable", "testing", "sid", "trixie", "bookworm", "forky"),
    default_arch="amd64",
    arch_choices=("amd64", "x86_64"),
    default_user="debian",
    default_hostname="ledit-debian",
    default_image_name="ledit-debian.img",
    build_script="ledit_core/backend/scripts/build-debian-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-debian-usb.sh",
    env_prefix="DEBIAN_USB",
    branch_env="DEBIAN_RELEASE",
    search_repos=DEBIAN_SEARCH_REPOS,
    validate_branch_func=validate_debian_release,
    validate_package_func=validate_deb_package_name,
    search_func=_search_debian,
)
