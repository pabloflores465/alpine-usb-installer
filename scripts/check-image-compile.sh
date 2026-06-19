#!/usr/bin/env bash
# Verify image configuration compiles into concrete Alpine/Slackware build plans.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
SLACKWARE_LOG="$WORK_DIR/slackware.log"
ALPINE_LOG="$WORK_DIR/alpine.log"
mkdir -p "$WORK_DIR"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

run_logged() {
  local log="$1"
  shift
  echo "+ $*" | tee "$log"
  "$@" 2>&1 | tee -a "$log"
}

assert_log_contains() {
  local log="$1"
  local pattern="$2"
  local description="$3"
  grep -Eq "$pattern" "$log" || fail "$description (see $log)"
}

echo "== Python package compile check =="
python3 -m compileall alpine_usb

echo "== Shell syntax checks =="
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-slackware-usb.sh \
  configure-slackware-usb.sh

echo "== Slackware CLI dry-run image plan =="
run_logged "$SLACKWARE_LOG" \
  ./alpine-usb build \
  --distro slackware \
  --slackware-release stable \
  --dry-run \
  --password testpass \
  --extra-package vim \
  --wm i3 \
  -y
assert_log_contains "$SLACKWARE_LOG" '^Slackware USB configuration dry-run$' "Slackware dry-run success marker missing"
assert_log_contains "$SLACKWARE_LOG" '^Packages:$' "Slackware package plan header missing"
assert_log_contains "$SLACKWARE_LOG" '^  [A-Za-z0-9][A-Za-z0-9._+@%-]*$' "Slackware package plan is empty"
assert_log_contains "$SLACKWARE_LOG" '^  vim$' "Slackware extra package did not reach the concrete plan"
assert_log_contains "$SLACKWARE_LOG" '^  i3$' "Slackware window-manager package did not reach the concrete plan"

echo "== Alpine CLI dry-run image plan =="
run_logged "$ALPINE_LOG" \
  ./alpine-usb build \
  --dry-run \
  --password testpass \
  --profile minimal \
  --desktop none \
  --display-manager none \
  --network none \
  --no-wifi \
  --no-bluetooth \
  --audio none \
  --browser none \
  --firmware none \
  -y
assert_log_contains "$ALPINE_LOG" '^DRY RUN OK$' "Alpine dry-run success marker missing"
assert_log_contains "$ALPINE_LOG" 'desktop=none' "Alpine no-desktop profile did not compile"
assert_log_contains "$ALPINE_LOG" '^ packages: .*[A-Za-z0-9]' "Alpine package/build plan is empty"

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" != "1" ]; then
  echo "Image compile check passed (dry-run plan mode). Set LINUX_USB_FULL_IMAGE_COMPILE=1 for gated full-build probing."
  exit 0
fi

echo "== Gated full Slackware image compile probe =="
SLACKWARE_FULL_LOG="$WORK_DIR/slackware-full.log"
SLACKWARE_FULL_IMG="$(pwd)/$WORK_DIR/slackware-full.img"
run_logged "$SLACKWARE_FULL_LOG" \
  ./alpine-usb build \
  --distro slackware \
  --slackware-release stable \
  --output "$SLACKWARE_FULL_IMG" \
  --password testpass \
  --desktop none \
  --display-manager none \
  --network none \
  --no-wifi \
  --no-bluetooth \
  --audio none \
  --browser none \
  --extra-package vim \
  --wm i3 \
  -y
[ -s "$SLACKWARE_FULL_IMG" ] || fail "Slackware full image compile did not create a non-empty image at $SLACKWARE_FULL_IMG"
assert_log_contains "$SLACKWARE_FULL_LOG" 'Slackware image written' "Slackware full image success marker missing"
echo "Image compile check passed (full Slackware artifact mode)."
