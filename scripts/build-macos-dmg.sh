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
  --collect-submodules "alpine_usb" \
  --add-data "build-alpine-usb.sh:." \
  --add-data "configure-alpine-usb.sh:." \
  --add-data "build-arch-usb.sh:." \
  --add-data "configure-arch-usb.sh:." \
  --add-data "build-debian-usb.sh:." \
  --add-data "configure-debian-usb.sh:." \
  --add-data "build-fedora-usb.sh:." \
  --add-data "build-gentoo-usb.sh:." \
  --add-data "configure-gentoo-usb.sh:." \
  --add-data "build-opensuse-usb.sh:." \
  --add-data "configure-opensuse-usb.sh:." \
  --add-data "build-rhel-usb.sh:." \
  --add-data "configure-rhel-usb.sh:." \
  --add-data "build-slackware-usb.sh:." \
  --add-data "configure-slackware-usb.sh:." \
  --add-data "build-ubuntu-usb.sh:." \
  --add-data "configure-ubuntu-usb.sh:." \
  --add-data "build-void-usb.sh:." \
  --add-data "configure-void-usb.sh:." \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "efi-fallback:efi-fallback" \
  --add-data "scripts/Dockerfile.builder:scripts" \
  --add-data "scripts/Dockerfile.gentoo-builder:scripts" \
  gui.py

cp -R "$DIST_DIR/$APP_NAME.app" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DIST_DIR/$DMG_NAME"

echo "DMG ready: $DIST_DIR/$DMG_NAME"
