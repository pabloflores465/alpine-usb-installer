from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.slackware_packages.index import SLACKWARE_RELEASES, search_official_slackware_packages
from ledit_core.slackware_packages.index import validate_package_name as validate_slackware_package_name
from ledit_core.slackware_packages.index import validate_release as validate_slackware_release


def _search_slackware(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_slackware_packages(branch, arch, query, limit)


SLACKWARE_PROVIDER = DistroProvider(
    id="slackware",
    label="Slackware",
    package_manager="pkgtools",
    default_branch="stable",
    branch_label="Slackware release",
    branch_help="stable, current, or 15.0",
    branch_choices=SLACKWARE_RELEASES,
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="slackware",
    default_hostname="ledit-slackware",
    default_image_name="ledit-slackware.img",
    build_script="ledit_core/backend/scripts/build-slackware-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-slackware-usb.sh",
    env_prefix="SLACKWARE_USB",
    script_env_prefix="LEDIT_USB",
    branch_env="SLACKWARE_RELEASE",
    search_repos=("a", "ap", "d", "k", "kde", "l", "n", "x", "xap", "xfce"),
    validate_branch_func=validate_slackware_release,
    validate_package_func=validate_slackware_package_name,
    search_func=_search_slackware,
    supports_systemd_boot=False,
)
