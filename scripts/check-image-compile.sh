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

SLACKWARE_FULL_LOG="$WORK_DIR/slackware-full.log"
set +e
run_logged "$SLACKWARE_FULL_LOG" \
  ./alpine-usb build \
  --distro slackware \
  --slackware-release stable \
  --output "$(pwd)/$WORK_DIR/slackware-full.img" \
  --password testpass \
  --extra-package vim \
  --wm i3 \
  -y
slackware_code=$?
set -e
if [ "$slackware_code" -eq 0 ]; then
  fail "Slackware full image compile unexpectedly succeeded; unsupported builds must not pretend success."
fi
assert_log_contains "$SLACKWARE_FULL_LOG" 'Slackware full image assembly is not implemented yet; use --dry-run for validated package/config planning\.' "Slackware unsupported-build message missing"
fail "Slackware full image compile is intentionally unsupported; see $SLACKWARE_FULL_LOG"

echo "== Gated full image compile probe =="
case "$(uname -s)" in
  Darwin)
    command -v docker >/dev/null 2>&1 || fail "Full image compile on macOS requires Docker Desktop; docker command not found."
    docker info >/dev/null 2>&1 || fail "Full image compile on macOS requires Docker Desktop to be running."
    ;;
  Linux)
    for tool in mtools grub-mkstandalone qemu-nbd parted rsync mkfs.vfat; do
      command -v "$tool" >/dev/null 2>&1 || fail "Full image compile on Linux requires '$tool'. Install build dependencies or unset LINUX_USB_FULL_IMAGE_COMPILE."
    done
    ;;
  *)
    fail "Full image compile is only supported on macOS with Docker or native Linux."
    ;;
esac

ALPINE_FULL_LOG="$WORK_DIR/alpine-full.log"
ALPINE_FULL_IMG="$(pwd)/$WORK_DIR/alpine-full.img"
run_logged "$ALPINE_FULL_LOG" \
  ./alpine-usb build \
  --output "$ALPINE_FULL_IMG" \
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
  --image-size 2G \
  -y
[ -s "$ALPINE_FULL_IMG" ] || fail "Alpine full image compile did not create a non-empty image at $ALPINE_FULL_IMG"

SLACKWARE_FULL_LOG="$WORK_DIR/slackware-full.log"
set +e
run_logged "$SLACKWARE_FULL_LOG" \
  ./alpine-usb build \
  --distro slackware \
  --slackware-release stable \
  --output "$(pwd)/$WORK_DIR/slackware-full.img" \
  --password testpass \
  --extra-package vim \
  --wm i3 \
  -y
slackware_code=$?
set -e
if [ "$slackware_code" -eq 0 ]; then
  fail "Slackware full image compile unexpectedly succeeded; unsupported builds must not pretend success."
fi
assert_log_contains "$SLACKWARE_FULL_LOG" 'Slackware full image assembly is not implemented yet; use --dry-run for validated package/config planning\.' "Slackware unsupported-build message missing"
fail "Slackware full image compile is intentionally unsupported; see $SLACKWARE_FULL_LOG"
