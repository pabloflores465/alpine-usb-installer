from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from alpine_usb.apk_packages.index import (
    APK_SEARCH_REPOS,
    search_official_apk_packages,
    validate_branch,
    validate_package_name,
)
from alpine_usb.linux_distros import gentoo


class LinuxDistroProvider(Protocol):
    name: str
    title: str
    package_kind: str
    default_branch: str
    default_user: str
    default_hostname: str

    def validate_branch(self, branch: str) -> str: ...

    def validate_package_name(self, package: str) -> str: ...

    def search_packages(self, branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]: ...

    def search_description(self, branch: str, arch: str) -> str: ...


@dataclass(frozen=True)
class AlpineProvider:
    name: str = "alpine"
    title: str = "Alpine Linux"
    package_kind: str = "APK"
    default_branch: str = "latest-stable"
    default_user: str = "alpine"
    default_hostname: str = "alpine-usb"

    def validate_branch(self, branch: str) -> str:
        return validate_branch(branch)

    def validate_package_name(self, package: str) -> str:
        return validate_package_name(package)

    def search_packages(self, branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
        return search_official_apk_packages(branch, arch, query, limit)

    def search_description(self, branch: str, arch: str) -> str:
        return f"Alpine {branch}/{arch} official repos: {', '.join(APK_SEARCH_REPOS)}"


@dataclass(frozen=True)
class GentooProvider:
    name: str = "gentoo"
    title: str = "Gentoo Linux"
    package_kind: str = "Portage"
    default_branch: str = "stable"
    default_user: str = "gentoo"
    default_hostname: str = "gentoo-usb"

    def validate_branch(self, branch: str) -> str:
        return gentoo.validate_branch(branch)

    def validate_package_name(self, package: str) -> str:
        return gentoo.validate_package_atom(package)

    def search_packages(self, branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
        self.validate_branch(branch)
        return gentoo.search_gentoo_packages(query, limit)

    def search_description(self, branch: str, arch: str) -> str:
        return f"Gentoo {branch}/{arch} package catalogue (curated mappings + local eix/pkgcore when available)"


_PROVIDERS: dict[str, LinuxDistroProvider] = {
    "alpine": AlpineProvider(),
    "gentoo": GentooProvider(),
}


def get_provider(name: str) -> LinuxDistroProvider:
    key = name.strip().lower()
    try:
        return _PROVIDERS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported distro: {name}") from exc
