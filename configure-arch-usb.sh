#!/bin/sh
# Validate and materialize Arch Linux USB configuration. In dry-run mode this is
# safe on any host; in build mode build-arch-usb.sh consumes the generated files.
set -eu

ROOT_DIR=${ROOT_DIR:-.work/arch-root}
DRY_RUN=${ALPINE_USB_DRY_RUN:-0}
PACKAGES_FILE=${ARCH_USB_PACKAGES_FILE:-.work/arch-packages.txt}
CONFIG_FILE=${ARCH_USB_CONFIG_FILE:-.work/arch-config.env}

python3 - "$PACKAGES_FILE" "$CONFIG_FILE" <<'PY'
from __future__ import annotations

import os
import shlex
import sys

from alpine_usb.build_profiles.arch import arch_packages_from_env
from alpine_usb.apk_packages.index import validate_package_name

packages_file, config_file = sys.argv[1:3]
env = dict(os.environ)
for key in ["ALPINE_USB_USER", "ALPINE_USB_HOSTNAME", "ALPINE_USB_TIMEZONE", "ALPINE_USB_LOCALE", "ALPINE_USB_CONSOLE_KEYMAP", "ALPINE_USB_XKB_LAYOUT"]:
    if not env.get(key):
        raise SystemExit(f"ERROR: {key} must not be empty")
for pkg in env.get("ALPINE_USB_EXTRA_PACKAGES", "").split():
    validate_package_name(pkg)
packages = arch_packages_from_env(env)
os.makedirs(os.path.dirname(packages_file) or ".", exist_ok=True)
with open(packages_file, "w", encoding="utf-8") as fh:
    fh.write("\n".join(packages) + "\n")
with open(config_file, "w", encoding="utf-8") as fh:
    for key in sorted(k for k in env if k.startswith("ALPINE_USB_") or k.startswith("ARCH_USB_") or k == "ARCH"):
        fh.write(f"{key}={shlex.quote(env[key])}\n")
print("Arch package set:")
print(" ".join(packages))
PY

if [ "$DRY_RUN" = "1" ]; then
  echo "Arch dry-run OK: wrote $PACKAGES_FILE and $CONFIG_FILE"
  exit 0
fi

echo "Arch configuration ready for pacstrap build in $ROOT_DIR"
