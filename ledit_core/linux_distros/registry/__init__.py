from __future__ import annotations

from ledit_core.linux_distros.models import DistroProvider
from ledit_core.linux_distros.registry.alpine import ALPINE_PROVIDER
from ledit_core.linux_distros.registry.arch import ARCH_PROVIDER
from ledit_core.linux_distros.registry.debian import DEBIAN_PROVIDER
from ledit_core.linux_distros.registry.fedora import FEDORA_PROVIDER
from ledit_core.linux_distros.registry.gentoo import GENTOO_PROVIDER
from ledit_core.linux_distros.registry.nixos import NIXOS_PROVIDER
from ledit_core.linux_distros.registry.opensuse import OPENSUSE_PROVIDER
from ledit_core.linux_distros.registry.rhel import RHEL_PROVIDER
from ledit_core.linux_distros.registry.slackware import SLACKWARE_PROVIDER
from ledit_core.linux_distros.registry.ubuntu import UBUNTU_PROVIDER
from ledit_core.linux_distros.registry.void import VOID_PROVIDER
from ledit_core.rhel_packages.packages import normalize_rhel_distro

PROVIDERS: tuple[DistroProvider, ...] = (
    ALPINE_PROVIDER,
    ARCH_PROVIDER,
    DEBIAN_PROVIDER,
    FEDORA_PROVIDER,
    GENTOO_PROVIDER,
    NIXOS_PROVIDER,
    OPENSUSE_PROVIDER,
    RHEL_PROVIDER,
    SLACKWARE_PROVIDER,
    UBUNTU_PROVIDER,
    VOID_PROVIDER,
)

DISTROS: dict[str, DistroProvider] = {provider.id: provider for provider in PROVIDERS}

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


__all__ = [
    "DISTROS",
    "PROVIDERS",
    "canonical_distro_id",
    "distro_choices",
    "get_distro",
    "rhel_variant_for_name",
]
