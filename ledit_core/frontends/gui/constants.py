from __future__ import annotations

import tempfile
from pathlib import Path

from ledit_core.linux_distros import get_distro

APP_TITLE = "LEDIT"
APP_SUBTITLE = "Linux External Drive Installer Tool"
DEFAULT_IMAGE_NAME = "ledit.img"
DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "ledit"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / get_distro("alpine").default_image_name
SAVED_CONFIG_PATH = Path.home() / ".config" / "ledit" / "gui-config.json"
CONFIG_FILE_FILTER = "JSON configuration (*.json);;YAML configuration (*.yaml *.yml)"
