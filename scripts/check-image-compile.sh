#!/usr/bin/env bash
# Compile image configuration into concrete dry-run build plans for supported distros.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
mkdir -p "$WORK_DIR"

log() { printf '[image-compile] %s\n' "$*"; }
fail() { printf '[image-compile] ERROR: %s\n' "$*" >&2; exit 1; }
skip() { printf '[image-compile] SKIP: %s\n' "$*"; }

assert_log_contains() {
  local file="$1" pattern="$2" description="$3"
  if ! grep -Eq "$pattern" "$file"; then
    printf '[image-compile] ERROR: %s not found in %s\n' "$description" "$file" >&2
    printf '[image-compile] ---- %s ----\n' "$file" >&2
    tail -n 80 "$file" >&2 || true
    exit 1
  fi
}

log "Compiling Python package"
python3 -m compileall alpine_usb

log "Checking shell syntax for build/config scripts"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-debian-usb.sh \
  configure-debian-usb.sh

DEBIAN_LOG="$WORK_DIR/debian.log"
ALPINE_LOG="$WORK_DIR/alpine.log"

log "Compiling Debian dry-run build plan -> $DEBIAN_LOG"
./alpine-usb build \
  --distro debian \
  --release stable \
  --dry-run \
  --password testpass \
  --profile minimal \
  -y >"$DEBIAN_LOG" 2>&1
assert_log_contains "$DEBIAN_LOG" 'Debian USB dry-run configuration OK' 'Debian dry-run success marker'
assert_log_contains "$DEBIAN_LOG" '^Packages:[[:space:]]+[[:alnum:]][[:alnum:].+:-]*' 'non-empty Debian package plan'
assert_log_contains "$DEBIAN_LOG" '^Profile:[[:space:]]+minimal' 'Debian profile plan'
assert_log_contains "$DEBIAN_LOG" '^Bootloader/kernel/firmware:[[:space:]]+' 'Debian boot plan'

log "Compiling Alpine dry-run build plan -> $ALPINE_LOG"
./alpine-usb build \
  --distro alpine \
  --dry-run \
  --password testpass \
  --profile minimal \
  -y >"$ALPINE_LOG" 2>&1
assert_log_contains "$ALPINE_LOG" 'DRY RUN OK' 'Alpine dry-run success marker'
assert_log_contains "$ALPINE_LOG" '^ packages:[[:space:]]+[[:alnum:]][[:alnum:].+:-]*' 'non-empty Alpine package plan'
assert_log_contains "$ALPINE_LOG" '^ desktop=none' 'Alpine minimal no-desktop plan'

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  log "Full image compile requested"
  case "$(uname -s)" in
    Darwin)
      command -v docker >/dev/null 2>&1 || fail "full Debian image compile on macOS requires Docker"
      docker info >/dev/null 2>&1 || fail "Docker is not running; start Docker Desktop for full Debian image compile"
      ;;
    Linux)
      if [ "$(id -u)" -ne 0 ] && ! sudo -n true >/dev/null 2>&1; then
        fail "full image compile requires root or passwordless sudo"
      fi
      missing_tools=()
      for tool in debootstrap parted losetup partx mkfs.vfat mkfs.ext4 grub-install; do
        if ! command -v "$tool" >/dev/null 2>&1; then
          missing_tools+=("$tool")
        fi
      done
      if [ "${#missing_tools[@]}" -gt 0 ]; then
        fail "full Debian image compile requires missing host tools: ${missing_tools[*]}"
      fi
      ;;
    *)
      fail "full Debian image compile requires Linux, or macOS with Docker"
      ;;
  esac

  FULL_LOG="$WORK_DIR/debian-full.log"
  FULL_OUTPUT="$PWD/$WORK_DIR/debian-full.img"
  rm -f "$FULL_OUTPUT"
  log "Building Debian image -> $FULL_OUTPUT (log: $FULL_LOG)"
  ./alpine-usb build \
    --distro debian \
    --release stable \
    --password testpass \
    --profile minimal \
    --image-size "${LINUX_USB_FULL_IMAGE_SIZE:-8G}" \
    --output "$FULL_OUTPUT" \
    -y >"$FULL_LOG" 2>&1 || {
      tail -n 120 "$FULL_LOG" >&2 || true
      fail "full Debian image compile failed; see $FULL_LOG"
    }
  [ -s "$FULL_OUTPUT" ] || fail "full image output is missing or empty: $FULL_OUTPUT"
fi

log "Image compile check passed. Logs are in $WORK_DIR"
