#!/usr/bin/env bash
# Verify image configurations compile into concrete build plans without requiring root.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
mkdir -p "$WORK_DIR"

log() { printf '[image-compile] %s\n' "$*"; }
fail() { printf '[image-compile] ERROR: %s\n' "$*" >&2; exit 1; }

assert_log_contains() {
  local file="$1"
  local pattern="$2"
  local message="$3"
  grep -Eq "$pattern" "$file" || fail "$message (see $file)"
}

log "Compiling Python package tree"
python3 -m compileall alpine_usb

log "Checking shell syntax for build/config scripts"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-void-usb.sh \
  configure-void-usb.sh

VOID_LOG="$WORK_DIR/void.log"
ALPINE_LOG="$WORK_DIR/alpine.log"

log "Compiling Void dry-run build plan through CLI -> $VOID_LOG"
./alpine-usb build \
  --distro void \
  --dry-run \
  --password testpass \
  --desktop none \
  --display-manager none \
  --no-wifi \
  --no-bluetooth \
  --audio none \
  --browser none \
  -y >"$VOID_LOG" 2>&1
assert_log_contains "$VOID_LOG" '^DRY RUN OK$' "Void dry-run did not report success"
assert_log_contains "$VOID_LOG" '^[[:space:]]*distro=void$' "Void dry-run did not use Void backend"
assert_log_contains "$VOID_LOG" '^[[:space:]]*packages:[[:space:]]+[^[:space:]]' "Void dry-run did not emit a non-empty package/build plan"

log "Compiling Alpine dry-run build plan through CLI -> $ALPINE_LOG"
./alpine-usb build \
  --distro alpine \
  --dry-run \
  --password testpass \
  --profile minimal \
  --desktop none \
  --display-manager none \
  --no-wifi \
  --no-bluetooth \
  --audio none \
  --browser none \
  -y >"$ALPINE_LOG" 2>&1
assert_log_contains "$ALPINE_LOG" '^DRY RUN OK$' "Alpine dry-run did not report success"
assert_log_contains "$ALPINE_LOG" '^[[:space:]]*packages:[[:space:]]+[^[:space:]]' "Alpine dry-run did not emit a non-empty package/build plan"

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  log "Full image compile requested"
  case "$(uname -s)" in
    Darwin)
      command -v docker >/dev/null 2>&1 || fail "Full Void image compile on macOS requires Docker"
      docker info >/dev/null 2>&1 || fail "Docker is not running; start Docker Desktop for full Void image compile"
      ;;
    Linux)
      if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        fail "Full Void image compile requires root for xbps-install -r and loop mounts"
      fi
      missing=()
      for tool in xbps-install xbps-reconfigure qemu-img parted mkfs.vfat mkfs.ext4 mount umount blkid losetup; do
        command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
      done
      if [ "${#missing[@]}" -ne 0 ]; then
        fail "Full Void image compile missing tools: ${missing[*]}"
      fi
      ;;
    *)
      fail "Full Void image compile requires Linux, or macOS with Docker"
      ;;
  esac
  FULL_LOG="$WORK_DIR/void-full.log"
  FULL_IMAGE="$(pwd)/$WORK_DIR/void-full.img"
  log "Building real Void image -> $FULL_IMAGE (log: $FULL_LOG)"
  ./alpine-usb build \
    --distro void \
    --password testpass \
    --desktop none \
    --display-manager none \
    --no-wifi \
    --no-bluetooth \
    --audio none \
    --browser none \
    --image-size "${LINUX_USB_FULL_IMAGE_SIZE:-8G}" \
    --output "$FULL_IMAGE" \
    -y >"$FULL_LOG" 2>&1
  [ -s "$FULL_IMAGE" ] || fail "Full image build did not create a non-empty image (see $FULL_LOG)"
fi

log "Image compile check passed."
