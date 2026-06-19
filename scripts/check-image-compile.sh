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

supports_alpine_full_build() {
  case "$(uname -s)" in
    Darwin)
      command -v docker >/dev/null 2>&1 || return 1
      docker info >/dev/null 2>&1 || return 1
      ;;
    Linux)
      for tool in curl sudo python3 mmd mcopy mdir; do
        command -v "$tool" >/dev/null 2>&1 || return 1
      done
      ;;
    *) return 1 ;;
  esac
}

if supports_alpine_full_build; then
  FULL_ALPINE_LOG="$WORK_DIR/alpine-full.log"
  FULL_ALPINE_IMG="$(pwd)/$WORK_DIR/alpine-full.img"
  log "Attempting full Alpine image build ($FULL_ALPINE_LOG)"
  ./alpine-usb build \
    --profile minimal \
    --password testpass \
    --output "$FULL_ALPINE_IMG" \
    -y >"$FULL_ALPINE_LOG" 2>&1
  [ -s "$FULL_ALPINE_IMG" ] || die "Full Alpine build did not produce $FULL_ALPINE_IMG"
else
  die "Full Alpine image compile requested, but this host lacks required Linux build tools or running Docker."
fi

FULL_GENTOO_LOG="$WORK_DIR/gentoo-full.log"
FULL_GENTOO_IMG="$(pwd)/$WORK_DIR/gentoo-full.img"
log "Attempting full Gentoo image build; this branch should fail with the known unsupported-build message ($FULL_GENTOO_LOG)"
set +e
./alpine-usb build \
  --distro gentoo \
  --password testpass \
  --output "$FULL_GENTOO_IMG" \
  -y >"$FULL_GENTOO_LOG" 2>&1
gentoo_code=$?
set -e
if [ "$gentoo_code" -eq 0 ]; then
  die "Gentoo full image build unexpectedly succeeded; update the image compile check for real Gentoo build support."
fi
assert_log_contains 'Gentoo full image build is not implemented in this branch yet' "$FULL_GENTOO_LOG"
die "Gentoo full image build is intentionally unsupported in this branch; see $FULL_GENTOO_LOG"
