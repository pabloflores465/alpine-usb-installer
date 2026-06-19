#!/usr/bin/env bash
# Compile image configuration into concrete dry-run build plans without requiring root/Docker.
set -euo pipefail

cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
UBUNTU_LOG="$WORK_DIR/ubuntu.log"
ALPINE_LOG="$WORK_DIR/alpine.log"
mkdir -p "$WORK_DIR"

log() { printf '==> %s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
skip() { printf 'SKIP: %s\n' "$*" >&2; exit 77; }
need() { command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"; }

assert_log_contains() {
  local pattern="$1"
  local file="$2"
  local message="$3"
  grep -Eq "$pattern" "$file" || fail "$message (see $file)"
}

log "Python compileall"
need python3
python3 -m compileall alpine_usb

log "Shell syntax checks"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-ubuntu-usb.sh \
  configure-ubuntu-usb.sh

log "Ubuntu dry-run build plan"
./alpine-usb build \
  --distro ubuntu \
  --release 24.04 \
  --dry-run \
  --password testpass \
  --profile minimal \
  -y >"$UBUNTU_LOG" 2>&1
assert_log_contains 'Ubuntu USB dry-run' "$UBUNTU_LOG" "Ubuntu dry-run success marker missing"
assert_log_contains '^Packages:[[:space:]]+[^[:space:]]+' "$UBUNTU_LOG" "Ubuntu dry-run package plan is empty"

log "Alpine dry-run build plan"
./alpine-usb build \
  --distro alpine \
  --dry-run \
  --password testpass \
  --profile minimal \
  -y >"$ALPINE_LOG" 2>&1
assert_log_contains 'DRY RUN OK' "$ALPINE_LOG" "Alpine dry-run success marker missing"
assert_log_contains '^[[:space:]]*packages:[[:space:]]+[^[:space:]]+' "$ALPINE_LOG" "Alpine dry-run package plan is empty"

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  log "Full Ubuntu image compile"
  case "$(uname -s)" in
    Darwin)
      command -v docker >/dev/null 2>&1 || skip "Docker is required for full image compile on macOS"
      docker info >/dev/null 2>&1 || skip "Docker is not running; start Docker Desktop for full image compile"
      ;;
    Linux)
      for cmd in sudo debootstrap sgdisk mkfs.vfat mkfs.ext4 losetup partprobe chroot rsync grub-install; do
        command -v "$cmd" >/dev/null 2>&1 || skip "missing $cmd; host does not support full image compile"
      done
      if [ "$(id -u)" != "0" ] && ! sudo -n true >/dev/null 2>&1; then
        skip "passwordless sudo or root is required for full image compile"
      fi
      ;;
    *)
      skip "full image compile is unsupported on $(uname -s)"
      ;;
  esac

  ./alpine-usb build \
    --distro ubuntu \
    --release 24.04 \
    --password testpass \
    --profile minimal \
    --image-size "${LINUX_USB_FULL_IMAGE_SIZE:-8G}" \
    --output "$PWD/$WORK_DIR/ubuntu-full.img" \
    -y >"$WORK_DIR/ubuntu-full.log" 2>&1 || fail "full Ubuntu image compile failed (see $WORK_DIR/ubuntu-full.log)"
  test -s "$WORK_DIR/ubuntu-full.img" || fail "full image compile did not create $WORK_DIR/ubuntu-full.img"
fi

log "Image compile check passed. Logs: $UBUNTU_LOG $ALPINE_LOG"
