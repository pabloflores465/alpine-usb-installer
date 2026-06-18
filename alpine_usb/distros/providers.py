from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alpine_usb.apk_packages.index import (
    APK_SEARCH_REPOS,
    search_official_apk_packages,
    validate_branch,
    validate_package_name,
)
from alpine_usb.void_packages.index import search_official_void_packages, validate_void_repository


@dataclass(frozen=True)
class DistroProvider:
    id: str
    label: str
    default_image_name: str
    default_branch: str
    default_arch: str
    package_manager_label: str
    configure_script: str
    build_script: str
    supports_systemd_boot: bool = True

    def validate_branch(self, branch: str) -> str:
        if self.id == "void":
            return validate_void_repository(branch)
        return validate_branch(branch)

    def validate_package_name(self, package: str) -> str:
        return validate_package_name(package)

    def search_packages(self, branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
        self.validate_branch(branch)
        if self.id == "void":
            return search_official_void_packages(branch, arch, query, limit)
        return search_official_apk_packages(branch, arch, query, limit)

    def repo_description(self, branch: str, arch: str) -> str:
        if self.id == "void":
            return f"Void {branch}/{arch} official binary repository"
        return f"Alpine {branch}/{arch} official repos: {', '.join(APK_SEARCH_REPOS)}"

    def script_path(self, root: Path, *, dry_run: bool = False) -> Path:
        return root / (self.configure_script if dry_run else self.build_script)


DISTROS: dict[str, DistroProvider] = {
    "alpine": DistroProvider(
        id="alpine",
        label="Alpine Linux",
        default_image_name="alpine-usb.img",
        default_branch="latest-stable",
        default_arch="x86_64",
        package_manager_label="APK",
        configure_script="configure-alpine-usb.sh",
        build_script="build-alpine-usb.sh",
    ),
    "void": DistroProvider(
        id="void",
        label="Void Linux (glibc)",
        default_image_name="void-usb.img",
        default_branch="current",
        default_arch="x86_64",
        package_manager_label="XBPS",
        configure_script="configure-void-usb.sh",
        build_script="build-void-usb.sh",
    ),
}


def get_distro(name: str) -> DistroProvider:
    key = name.lower()
    try:
        return DISTROS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported distro: {name}") from exc
