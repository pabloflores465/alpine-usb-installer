from __future__ import annotations

from ledit_core.linux_distros.gentoo import search_gentoo_packages, validate_package_atom
from ledit_core.linux_distros.gentoo import validate_branch as validate_gentoo_branch
from ledit_core.linux_distros.models import DistroProvider


def _search_gentoo(_branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_gentoo_packages(query, limit)


GENTOO_PROVIDER = DistroProvider(
    id="gentoo",
    label="Gentoo",
    package_manager="Portage",
    default_branch="stable",
    branch_label="Gentoo branch",
    branch_help="stable or testing",
    branch_choices=("stable", "testing"),
    default_arch="x86_64",
    arch_choices=("x86_64", "amd64"),
    default_user="gentoo",
    default_hostname="ledit-gentoo",
    default_image_name="ledit-gentoo.img",
    build_script="ledit_core/backend/scripts/build-gentoo-usb.sh",
    configure_script="ledit_core/backend/scripts/configure-gentoo-usb.sh",
    env_prefix="GENTOO_USB",
    script_env_prefix="LEDIT_USB",
    branch_env="GENTOO_STAGE3_BRANCH",
    search_repos=("gentoo", "local-portage"),
    validate_branch_func=validate_gentoo_branch,
    validate_package_func=validate_package_atom,
    search_func=_search_gentoo,
    supports_systemd_boot=False,
)
