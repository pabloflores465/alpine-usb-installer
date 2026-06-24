from __future__ import annotations

from ledit_core.apt_packages.index import APT_SEARCH_REPOS, search_official_apt_packages, validate_ubuntu_release
from ledit_core.deb_packages.index import validate_package_name as validate_deb_package_name
from ledit_core.linux_distros.models import DistroProvider


def _search_ubuntu(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_apt_packages(branch, arch, query, limit)


UBUNTU_PROVIDER = DistroProvider(
    id="ubuntu",
    label="Ubuntu",
    package_manager="APT",
    default_branch="24.04",
    branch_label="Ubuntu release",
    branch_help="24.04/noble or 22.04/jammy",
    branch_choices=("24.04", "noble", "22.04", "jammy"),
    default_arch="x86_64",
    arch_choices=("x86_64", "amd64"),
    default_user="ubuntu",
    default_hostname="ledit-ubuntu",
    default_image_name="ledit-ubuntu.img",
    build_script="backend/scripts/build-ubuntu-usb.sh",
    configure_script="backend/scripts/configure-ubuntu-usb.sh",
    env_prefix="UBUNTU_USB",
    branch_env="UBUNTU_RELEASE",
    search_repos=APT_SEARCH_REPOS,
    validate_branch_func=validate_ubuntu_release,
    validate_package_func=validate_deb_package_name,
    search_func=_search_ubuntu,
)
