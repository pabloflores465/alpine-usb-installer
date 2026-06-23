from __future__ import annotations

from ledit_core.apk_packages.index import APK_SEARCH_REPOS, search_official_apk_packages
from ledit_core.apk_packages.index import validate_branch as validate_apk_branch
from ledit_core.apk_packages.index import validate_package_name as validate_apk_package_name
from ledit_core.apt_packages.index import APT_SEARCH_REPOS, search_official_apt_packages, validate_ubuntu_release
from ledit_core.arch_packages.index import (
    ARCH_SEARCH_REPOS,
    search_official_arch_packages,
    validate_arch_branch,
    validate_arch_package_name,
)
from ledit_core.deb_packages.index import DEBIAN_SEARCH_REPOS, search_official_deb_packages
from ledit_core.deb_packages.index import validate_package_name as validate_deb_package_name
from ledit_core.deb_packages.index import validate_release as validate_debian_release
from ledit_core.fedora_packages.index import search_fedora_packages, validate_fedora_package_name
from ledit_core.linux_distros.fedora import validate_release as validate_fedora_release
from ledit_core.linux_distros.gentoo import search_gentoo_packages, validate_package_atom
from ledit_core.linux_distros.gentoo import validate_branch as validate_gentoo_branch
from ledit_core.linux_distros.models import DistroProvider
from ledit_core.linux_distros.opensuse import (
    OPENSUSE_SEARCH_REPOS,
    search_official_opensuse_packages,
    validate_opensuse_release,
)
from ledit_core.linux_distros.opensuse import validate_package_name as validate_opensuse_package_name
from ledit_core.nixos.packages import (
    NIXOS_DEFAULT_CHANNEL,
    NIXOS_STABLE_CHANNELS,
    search_nix_packages,
    validate_nix_channel,
    validate_nix_package_name,
)
from ledit_core.rhel_packages.packages import (
    RHEL_DEFAULT_RELEASE,
    normalize_rhel_distro,
    search_rhel_packages,
    validate_rhel_release,
)
from ledit_core.rhel_packages.packages import (
    validate_package_name as validate_rhel_package_name,
)
from ledit_core.slackware_packages.index import (
    SLACKWARE_RELEASES,
    search_official_slackware_packages,
)
from ledit_core.slackware_packages.index import (
    validate_package_name as validate_slackware_package_name,
)
from ledit_core.slackware_packages.index import (
    validate_release as validate_slackware_release,
)
from ledit_core.void_packages.index import (
    search_official_void_packages,
    validate_void_repository,
)
from ledit_core.void_packages.index import (
    validate_package_name as validate_void_package_name,
)


def _search_alpine(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_apk_packages(branch, arch, query, limit)


def _search_arch(_branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_arch_packages(query, arch, limit)


def _search_debian(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_deb_packages(branch, arch, query, limit)


def _search_fedora(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_fedora_packages(branch, arch, query, limit)


def _search_gentoo(_branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_gentoo_packages(query, limit)


def _search_nixos(branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_nix_packages(branch, query, limit)


def _search_opensuse(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_opensuse_packages(branch, arch, query, limit)


def _search_rhel(branch: str, _arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_rhel_packages("rocky", branch, query, limit)


def _search_slackware(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_slackware_packages(branch, arch, query, limit)


def _search_ubuntu(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_apt_packages(branch, arch, query, limit)


def _search_void(branch: str, arch: str, query: str, limit: int) -> list[dict[str, str]]:
    return search_official_void_packages(branch, arch, query, limit)


DISTROS: dict[str, DistroProvider] = {
    "alpine": DistroProvider(
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
        build_script="build-alpine-usb.sh",
        configure_script="configure-alpine-usb.sh",
        env_prefix="LEDIT_USB",
        branch_env="ALPINE_BRANCH",
        search_repos=APK_SEARCH_REPOS,
        validate_branch_func=validate_apk_branch,
        validate_package_func=validate_apk_package_name,
        search_func=_search_alpine,
    ),
    "arch": DistroProvider(
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
        build_script="build-arch-usb.sh",
        configure_script="configure-arch-usb.sh",
        env_prefix="ARCH_USB",
        script_env_prefix="LEDIT_USB",
        branch_env="ARCH_USB_BRANCH",
        search_repos=ARCH_SEARCH_REPOS,
        validate_branch_func=validate_arch_branch,
        validate_package_func=validate_arch_package_name,
        search_func=_search_arch,
    ),
    "debian": DistroProvider(
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
        build_script="build-debian-usb.sh",
        configure_script="configure-debian-usb.sh",
        env_prefix="DEBIAN_USB",
        branch_env="DEBIAN_RELEASE",
        search_repos=DEBIAN_SEARCH_REPOS,
        validate_branch_func=validate_debian_release,
        validate_package_func=validate_deb_package_name,
        search_func=_search_debian,
    ),
    "fedora": DistroProvider(
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
        build_script="build-fedora-usb.sh",
        configure_script=None,
        env_prefix="FEDORA_USB",
        branch_env="FEDORA_RELEASE",
        search_repos=("fedora", "updates"),
        validate_branch_func=validate_fedora_release,
        validate_package_func=validate_fedora_package_name,
        search_func=_search_fedora,
        supports_dry_run_script=False,
    ),
    "gentoo": DistroProvider(
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
        build_script="build-gentoo-usb.sh",
        configure_script="configure-gentoo-usb.sh",
        env_prefix="GENTOO_USB",
        script_env_prefix="LEDIT_USB",
        branch_env="GENTOO_STAGE3_BRANCH",
        search_repos=("gentoo", "local-portage"),
        validate_branch_func=validate_gentoo_branch,
        validate_package_func=validate_package_atom,
        search_func=_search_gentoo,
        supports_systemd_boot=False,
    ),
    "nixos": DistroProvider(
        id="nixos",
        label="NixOS",
        package_manager="nixpkgs",
        default_branch=NIXOS_DEFAULT_CHANNEL,
        branch_label="NixOS channel",
        branch_help=", ".join(NIXOS_STABLE_CHANNELS),
        branch_choices=tuple(NIXOS_STABLE_CHANNELS),
        default_arch="x86_64-linux",
        arch_choices=("x86_64-linux", "x86_64"),
        default_user="nixos",
        default_hostname="ledit-nixos",
        default_image_name="ledit-nixos.img",
        build_script=None,
        configure_script=None,
        env_prefix="NIXOS_USB",
        branch_env="NIXOS_CHANNEL",
        search_repos=("nixpkgs",),
        validate_branch_func=validate_nix_channel,
        validate_package_func=validate_nix_package_name,
        search_func=_search_nixos,
        supports_dry_run_script=False,
        supports_gui_build_worker=False,
        supports_systemd_boot=False,
        supports_extlinux=True,
    ),
    "opensuse": DistroProvider(
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
        build_script="build-opensuse-usb.sh",
        configure_script="configure-opensuse-usb.sh",
        env_prefix="OPENSUSE_USB",
        branch_env="OPENSUSE_RELEASE",
        search_repos=OPENSUSE_SEARCH_REPOS,
        validate_branch_func=validate_opensuse_release,
        validate_package_func=validate_opensuse_package_name,
        search_func=_search_opensuse,
    ),
    "rhel": DistroProvider(
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
        build_script="build-rhel-usb.sh",
        configure_script="configure-rhel-usb.sh",
        env_prefix="RHEL_USB",
        branch_env="RHEL_USB_RELEASE",
        search_repos=("baseos", "appstream"),
        validate_branch_func=validate_rhel_release,
        validate_package_func=validate_rhel_package_name,
        search_func=_search_rhel,
        rhel_variant="rocky",
    ),
    "slackware": DistroProvider(
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
        build_script="build-slackware-usb.sh",
        configure_script="configure-slackware-usb.sh",
        env_prefix="SLACKWARE_USB",
        script_env_prefix="LEDIT_USB",
        branch_env="SLACKWARE_RELEASE",
        search_repos=("a", "ap", "d", "k", "kde", "l", "n", "x", "xap", "xfce"),
        validate_branch_func=validate_slackware_release,
        validate_package_func=validate_slackware_package_name,
        search_func=_search_slackware,
        supports_systemd_boot=False,
    ),
    "ubuntu": DistroProvider(
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
        build_script="build-ubuntu-usb.sh",
        configure_script="configure-ubuntu-usb.sh",
        env_prefix="UBUNTU_USB",
        branch_env="UBUNTU_RELEASE",
        search_repos=APT_SEARCH_REPOS,
        validate_branch_func=validate_ubuntu_release,
        validate_package_func=validate_apk_package_name,
        search_func=_search_ubuntu,
    ),
    "void": DistroProvider(
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
        build_script="build-void-usb.sh",
        configure_script="configure-void-usb.sh",
        env_prefix="VOID_USB",
        script_env_prefix="LEDIT_USB",
        branch_env="VOID_REPOSITORY",
        search_repos=("current",),
        validate_branch_func=validate_void_repository,
        validate_package_func=validate_void_package_name,
        search_func=_search_void,
    ),
}

_DISTRO_ALIASES = {
    "rocky": "rhel",
    "rockylinux": "rhel",
    "alma": "rhel",
    "almalinux": "rhel",
    "centos": "rhel",
    "centos-stream": "rhel",
    "opensuse-tumbleweed": "opensuse",
    "suse": "opensuse",
}


def distro_choices(*, include_aliases: bool = False, visible_only: bool = False) -> tuple[str, ...]:
    names = [name for name, provider in DISTROS.items() if not visible_only or provider.visible]
    if include_aliases:
        names.extend(_DISTRO_ALIASES)
    return tuple(sorted(names))


def get_distro(name: str | None) -> DistroProvider:
    key = (name or "alpine").strip().lower()
    key = _DISTRO_ALIASES.get(key, key)
    try:
        return DISTROS[key]
    except KeyError as exc:
        allowed = ", ".join(distro_choices(include_aliases=True))
        raise ValueError(f"Unsupported distro: {name}. Supported: {allowed}") from exc


def canonical_distro_id(name: str | None) -> str:
    return get_distro(name).id


def rhel_variant_for_name(name: str | None) -> str:
    key = (name or "rhel").strip().lower()
    if key in {"rocky", "rockylinux"}:
        return "rocky"
    if key in {"alma", "almalinux"}:
        return "alma"
    if key in {"centos", "centos-stream", "stream"}:
        return "centos-stream"
    if key == "rhel":
        return "rocky"
    return normalize_rhel_distro(key)
