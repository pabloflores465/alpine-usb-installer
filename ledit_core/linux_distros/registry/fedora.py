from __future__ import annotations

from ledit_core.fedora_packages.index import search_fedora_packages, validate_fedora_package_name
from ledit_core.linux_distros.fedora import validate_release as validate_fedora_release
from ledit_core.linux_distros.models import DistroProvider


def _search_fedora(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_fedora_packages(branch, arch, query, limit)


FEDORA_PROVIDER = DistroProvider(
    id="fedora",
    label="Fedora",
    package_manager="DNF",
    default_branch="stable",
    branch_label="Fedora release",
    branch_help="stable, latest, rawhide, or a numeric release such as 42",
    branch_choices=("stable", "latest", "rawhide", "42", "41"),
    default_arch="x86_64",
    arch_choices=("x86_64",),
    default_user="fedora",
    default_hostname="ledit-fedora",
    default_image_name="ledit-fedora.img",
    build_script="ledit_core/backend/scripts/build-fedora-usb.sh",
    configure_script=None,
    env_prefix="FEDORA_USB",
    branch_env="FEDORA_RELEASE",
    search_repos=("fedora", "updates"),
    validate_branch_func=validate_fedora_release,
    validate_package_func=validate_fedora_package_name,
    search_func=_search_fedora,
    supports_dry_run_script=False,
)
