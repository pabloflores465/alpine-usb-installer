from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PackageSearch = Callable[[str, str, str, int], list[dict[str, str]]]
PackageValidator = Callable[[str], object]
BranchValidator = Callable[[str], object]


@dataclass(frozen=True)
class DistroProvider:
    id: str
    label: str
    package_manager: str
    default_branch: str
    branch_label: str
    branch_help: str
    branch_choices: tuple[str, ...]
    default_arch: str
    arch_choices: tuple[str, ...]
    default_user: str
    default_hostname: str
    default_image_name: str
    build_script: str | None
    configure_script: str | None
    env_prefix: str
    branch_env: str
    search_repos: tuple[str, ...]
    validate_branch_func: BranchValidator
    validate_package_func: PackageValidator
    search_func: PackageSearch | None
    supports_dry_run_script: bool = True
    supports_gui_build_worker: bool = True
    supports_systemd_boot: bool = True
    supports_extlinux: bool = False
    script_env_prefix: str | None = None
    rhel_variant: str | None = None
    visible: bool = True

    @property
    def script_prefix(self) -> str:
        return self.script_env_prefix or self.env_prefix

    def normalize_branch(self, branch: str | None) -> str:
        value = (branch or "").strip() or self.default_branch
        if self.id != "alpine" and value == "latest-stable":
            value = self.default_branch
        validated = self.validate_branch_func(value)
        # Validators in older helper modules sometimes return None on success.
        return value if validated is None else str(validated)

    def normalize_arch(self, arch: str | None) -> str:
        value = (arch or self.default_arch).strip() or self.default_arch
        if value not in self.arch_choices:
            allowed = ", ".join(self.arch_choices)
            raise ValueError(f"{self.label} architecture must be one of: {allowed}")
        return value

    def validate_package_name(self, package: str) -> str:
        validated = self.validate_package_func(package)
        return package if validated is None else str(validated)

    def search_packages(self, branch: str, arch: str, query: str, limit: int = 10) -> list[dict[str, str]]:
        if self.search_func is None:
            raise RuntimeError(f"Package search is not implemented for {self.label}")
        branch = self.normalize_branch(branch)
        arch = self.normalize_arch(arch)
        return self.search_func(branch, arch, query, limit)

    def repo_description(self, branch: str, arch: str) -> str:
        branch = self.normalize_branch(branch)
        arch = self.normalize_arch(arch)
        repos = ", ".join(self.search_repos) if self.search_repos else self.package_manager
        return f"{self.label} {branch}/{arch} {self.package_manager} repos: {repos}"

    def build_script_path(self, root: Path) -> Path | None:
        return root / self.build_script if self.build_script else None

    def configure_script_path(self, root: Path) -> Path | None:
        return root / self.configure_script if self.configure_script else None
