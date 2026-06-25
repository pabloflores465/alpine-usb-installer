from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.rhel_packages.packages import RHEL_DEFAULT_RELEASE, search_rhel_packages, validate_rhel_release
from ledit_core.rhel_packages.packages import validate_package_name as validate_rhel_package_name


def _search_rhel(branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_rhel_packages("rocky", branch, query, limit)


RHEL_PROVIDER = DistroProvider(
    id="rhel",
    label="RHEL family (Rocky Linux compatible)",
    package_manager="DNF",
    default_branch=RHEL_DEFAULT_RELEASE,
    branch_label="RHEL-family release",
    branch_help="major release such as 9 or 10",
    branch_choices=("9", "10"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="linux",
    default_hostname="ledit-rhel",
    default_image_name="ledit-rhel.img",
    build_script="ledit_core/backend/scripts/build-rhel-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-rhel-usb.sh",
    env_prefix="RHEL_USB",
    branch_env="RHEL_USB_RELEASE",
    search_repos=("baseos", "appstream"),
    validate_branch_func=validate_rhel_release,
    validate_package_func=validate_rhel_package_name,
    search_func=_search_rhel,
    rhel_variant="rocky",
)
