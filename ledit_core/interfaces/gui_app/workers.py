from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, QTimer, Signal

from ledit_core.image_builds.execution import ImageBuildRunner
from ledit_core.package_search import DistroPackageSearchService, PackageSearchRequest
from ledit_core.usb_devices.detection import list_devices


class DeviceScanWorker(QThread):
    done = Signal(list)

    def run(self):
        self.done.emit(list_devices())


class PackageSearchWorker(QThread):
    done = Signal(str, list)
    failed = Signal(str, str)

    def __init__(
        self,
        distro: str,
        branch: str,
        arch: str,
        query: str,
        search_service_factory: Callable[[], DistroPackageSearchService] = DistroPackageSearchService,
    ):
        super().__init__()
        self.distro = distro
        self.branch = branch
        self.arch = arch
        self.query = query
        self.search_service_factory = search_service_factory

    def run(self):
        try:
            results = self.search_service_factory().search(
                PackageSearchRequest(distro=self.distro, branch=self.branch, arch=self.arch, query=self.query, limit=10)
            )
            self.done.emit(self.query, results)
        except Exception as exc:
            self.failed.emit(self.query, str(exc))


class BuildWorker(QThread):
    log = Signal(str)
    done = Signal(bool, str)

    def __init__(self, config_env: dict[str, str], output_path: str, runner: ImageBuildRunner):
        super().__init__()
        self.config_env = config_env
        self.output_path = output_path
        self.runner = runner

    def force_cancel(self):
        self.runner.force_cancel(self.log.emit)

    def cancel(self):
        self.runner.cancel(self.log.emit)
        QTimer.singleShot(5000, self.force_cancel)

    def run(self):
        result = self.runner.run({k: str(v) for k, v in self.config_env.items()}, self.output_path, self.log.emit)
        self.done.emit(result.ok, result.message)


# Backward-compatible local name used by gui.py until UI wording is fully renamed.
ApkSearchWorker = PackageSearchWorker
