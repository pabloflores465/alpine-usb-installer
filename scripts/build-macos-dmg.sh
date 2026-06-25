#!/usr/bin/env bash
# Build macOS DMG containing only the Qt GUI app.
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="LEDIT"
DMG_NAME="LEDIT.dmg"
BUILD_DIR="build"
DIST_DIR="dist"
STAGE_DIR="$BUILD_DIR/dmg-root"
if [ -n "${PYINSTALLER:-}" ]; then
  PYINSTALLER_CMD="$PYINSTALLER"
elif [ -x ".qtvenv/bin/pyinstaller" ]; then
  PYINSTALLER_CMD=".qtvenv/bin/pyinstaller"
else
  PYINSTALLER_CMD="pyinstaller"
fi

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script builds a macOS DMG and must run on macOS." >&2
  exit 1
fi

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required tool: $1" >&2
    exit 1
  }
}

need "$PYINSTALLER_CMD"
need hdiutil

rm -rf "$BUILD_DIR" "$DIST_DIR" "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

"$PYINSTALLER_CMD" \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --collect-submodules "ledit_core" \
  --add-data "ledit_core/backend/scripts/build-alpine-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-alpine-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-arch-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-arch-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-debian-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-debian-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-fedora-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-gentoo-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-gentoo-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-opensuse-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-opensuse-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-rhel-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-rhel-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-slackware-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-slackware-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-ubuntu-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-ubuntu-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-void-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-void-usb.sh:ledit_core/backend/scripts" \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "ledit_core/backend/efi-fallback:ledit_core/backend/efi-fallback" \
  --add-data "ledit_core/backend/docker/Dockerfile.builder:ledit_core/backend/docker" \
  --add-data "ledit_core/backend/docker/Dockerfile.gentoo-builder:ledit_core/backend/docker" \
  ledit_core/frontends/gui/app.py

cp -R "$DIST_DIR/$APP_NAME.app" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DIST_DIR/$DMG_NAME"

echo "DMG ready: $DIST_DIR/$DMG_NAME"
