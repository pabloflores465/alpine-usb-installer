from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ledit_core.linux_distros import DistroProvider, get_distro

ProviderLookup = Callable[[str | None], DistroProvider]


@dataclass(frozen=True)
class PackageSearchRequest:
    distro: str
    branch: str
    arch: str
    query: str
    limit: int = 10


class PackageSearchPort(Protocol):
    def search(self, request: PackageSearchRequest) -> list[dict[str, str]]: ...

    def repo_description(self, distro: str, branch: str, arch: str) -> str: ...


class DistroPackageSearchService:
    def __init__(self, provider_lookup: ProviderLookup = get_distro):
        self.provider_lookup = provider_lookup

    def provider(self, distro: str | None) -> DistroProvider:
        return self.provider_lookup(distro)

    def search(self, request: PackageSearchRequest) -> list[dict[str, str]]:
        provider = self.provider(request.distro)
        return provider.search_packages(request.branch, request.arch, request.query, request.limit)

    def repo_description(self, distro: str, branch: str, arch: str) -> str:
        provider = self.provider(distro)
        return provider.repo_description(branch, arch)

    def validate_selection(self, distro: str, branch: str, arch: str, packages: list[str]) -> list[str]:
        provider = self.provider(distro)
        missing: list[str] = []
        for package in packages:
            provider.validate_package_name(package)
            results = provider.search_packages(branch, arch, package, 50)
            if not any(result.get("name") == package for result in results):
                missing.append(package)
        return missing
