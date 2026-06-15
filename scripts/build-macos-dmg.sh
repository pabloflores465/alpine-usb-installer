#!/usr/bin/env bash
# Build macOS DMG containing the Qt app plus the unified terminal utility.
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="Alpine USB Installer"
DMG_NAME="Alpine USB Installer.dmg"
BUILD_DIR="build"
DIST_DIR="dist"
STAGE_DIR="$BUILD_DIR/dmg-root"
TERMINAL_DIR="$STAGE_DIR/Terminal"
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
mkdir -p "$TERMINAL_DIR"

"$PYINSTALLER_CMD" \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --add-data "build-alpine-usb.sh:." \
  --add-data "configure-alpine-usb.sh:." \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "efi-fallback:efi-fallback" \
  gui.py

"$PYINSTALLER_CMD" \
  --noconfirm \
  --onefile \
  --console \
  --name "alpine-usb" \
  --hidden-import "cli" \
  --hidden-import "tui" \
  --add-data "build-alpine-usb.sh:." \
  --add-data "configure-alpine-usb.sh:." \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "efi-fallback:efi-fallback" \
  alpine-usb

cp -R "$DIST_DIR/$APP_NAME.app" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

cp "$DIST_DIR/alpine-usb" "$TERMINAL_DIR/alpine-usb"
cp README.md LICENSE "$TERMINAL_DIR/"
chmod 755 "$TERMINAL_DIR/alpine-usb"
cat > "$TERMINAL_DIR/README-Terminal.txt" <<'EOF'
Alpine USB Installer terminal utility

Run from Terminal:

  cd /Volumes/Alpine\ USB\ Installer/Terminal
  ./alpine-usb          # opens TUI
  ./alpine-usb --help   # CLI commands

You can also copy this Terminal folder anywhere writable and run ./alpine-usb there.
The terminal binary is standalone; build resources are copied automatically to /tmp/alpine-usb-installer/terminal-runtime at runtime.
EOF

cat > "$STAGE_DIR/Open Terminal Utility.command" <<'EOF'
#!/bin/zsh
cd "$(dirname "$0")/Terminal" || exit 1
exec ./alpine-usb
EOF
chmod 755 "$STAGE_DIR/Open Terminal Utility.command"

hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DIST_DIR/$DMG_NAME"

echo "DMG ready: $DIST_DIR/$DMG_NAME"
