#!/usr/bin/env bash
# Validate that image options compile into concrete Alpine/Gentoo build plans.
# Default mode is dry-run only: no root, Docker, or full image build required.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
mkdir -p "$WORK_DIR"

log() { printf '[image-compile] %s\n' "$*"; }
die() { printf '[image-compile] ERROR: %s\n' "$*" >&2; exit 1; }

assert_log_contains() {
  needle="$1"
  file="$2"
  grep -q "$needle" "$file" || die "Expected '$needle' in $file"
}

assert_package_plan() {
  file="$1"
  if ! grep -Eq '^(Packages:| packages:).*[^[:space:]]' "$file"; then
    die "Expected a non-empty package/build plan in $file"
  fi
}

log "Compiling Python package"
python3 -m compileall alpine_usb

log "Checking shell syntax"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-gentoo-usb.sh \
  configure-gentoo-usb.sh \
  scripts/check-image-compile.sh

GENTOO_LOG="$WORK_DIR/gentoo.log"
ALPINE_LOG="$WORK_DIR/alpine.log"

log "Dry-running Gentoo image plan via CLI ($GENTOO_LOG)"
./alpine-usb build \
  --distro gentoo \
  --dry-run \
  --password testpass \
  --extra-package app-misc/ranger \
  -y >"$GENTOO_LOG" 2>&1
assert_log_contains 'Gentoo USB dry-run OK' "$GENTOO_LOG"
assert_log_contains 'Package count: [1-9]' "$GENTOO_LOG"
assert_log_contains 'app-misc/ranger' "$GENTOO_LOG"
assert_package_plan "$GENTOO_LOG"

log "Dry-running minimal Alpine image plan via CLI ($ALPINE_LOG)"
./alpine-usb build \
  --profile minimal \
  --dry-run \
  --password testpass \
  -y >"$ALPINE_LOG" 2>&1
assert_log_contains 'DRY RUN OK' "$ALPINE_LOG"
assert_log_contains 'desktop=none' "$ALPINE_LOG"
assert_package_plan "$ALPINE_LOG"

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" != "1" ]; then
  log "Full image build skipped (set LINUX_USB_FULL_IMAGE_COMPILE=1 to attempt it)."
  log "Image compile check passed."
  exit 0
fi

FULL_GENTOO_LOG="$WORK_DIR/gentoo-full.log"
FULL_GENTOO_IMG="$(pwd)/$WORK_DIR/gentoo-full.img"
log "Attempting full Gentoo image build via verified official ISO fallback ($FULL_GENTOO_LOG)"
./alpine-usb build \
  --distro gentoo \
  --password testpass \
  --desktop none \
  --display-manager none \
  --network none \
  --no-wifi \
  --no-bluetooth \
  --audio none \
  --browser none \
  --output "$FULL_GENTOO_IMG" \
  -y >"$FULL_GENTOO_LOG" 2>&1
[ -s "$FULL_GENTOO_IMG" ] || die "Gentoo full image build did not produce $FULL_GENTOO_IMG"
assert_log_contains 'Gentoo image written' "$FULL_GENTOO_LOG"
log "Image compile check passed."
