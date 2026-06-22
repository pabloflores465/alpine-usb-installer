#!/usr/bin/env bash
# Compile-check generated image configuration through the real CLI without
# requiring root, Docker, or a full image build by default.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
mkdir -p "$WORK_DIR"

log() { printf '==> %s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

run_logged() {
  local logfile="$1"
  shift
  "$@" >"$logfile" 2>&1 || {
    local code=$?
    printf 'Command failed with exit code %s: %s\n' "$code" "$*" >&2
    printf '%s\n' "--- $logfile ---" >&2
    tail -n 80 "$logfile" >&2 || true
    exit "$code"
  }
}

assert_log_contains() {
  local logfile="$1"
  local pattern="$2"
  local message="$3"
  if ! grep -Eq "$pattern" "$logfile"; then
    printf 'Missing expected marker in %s: %s\n' "$logfile" "$message" >&2
    printf '%s\n' "--- $logfile ---" >&2
    tail -n 80 "$logfile" >&2 || true
    exit 1
  fi
}

log "Compiling Python package"
python3 -m compileall alpine_usb

log "Checking shell syntax"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-opensuse-usb.sh \
  configure-opensuse-usb.sh \
  scripts/check-image-compile.sh

opensuse_log="$WORK_DIR/opensuse.log"
log "Dry-running openSUSE image configuration through CLI ($opensuse_log)"
run_logged "$opensuse_log" \
  ./alpine-usb build \
    --distro opensuse \
    --release tumbleweed \
    --dry-run \
    --password testpass \
    --desktop none \
    --display-manager none \
    --no-wifi \
    --no-bluetooth \
    --audio none \
    --browser none \
    -y
assert_log_contains "$opensuse_log" 'openSUSE USB configuration plan' 'openSUSE success marker'
assert_log_contains "$opensuse_log" '^Packages:[[:space:]]*[^[:space:]]' 'non-empty openSUSE package plan'
assert_log_contains "$opensuse_log" 'Build profile|Boot:|Distro[[:space:]]+openSUSE' 'concrete openSUSE build plan'

alpine_log="$WORK_DIR/alpine.log"
log "Dry-running Alpine minimal no-desktop configuration through CLI ($alpine_log)"
run_logged "$alpine_log" \
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
assert_log_contains "$alpine_log" 'DRY RUN OK' 'Alpine dry-run success marker'
assert_log_contains "$alpine_log" '^ packages:[[:space:]]*[^[:space:]]' 'non-empty Alpine package plan'

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  full_log="$WORK_DIR/opensuse-full.log"
  full_image="$(pwd)/$WORK_DIR/opensuse-full.img"
  log "Full image compile gate enabled"
  case "$(uname -s)" in
    Darwin)
      have docker || fail "full openSUSE image compile on macOS requires Docker"
      docker info >/dev/null 2>&1 || fail "Docker is not running; start Docker Desktop for full openSUSE image compile"
      ;;
    Linux)
      missing=()
      for tool in zypper qemu-img parted mkfs.ext4 mkfs.fat losetup blkid findmnt chroot; do
        have "$tool" || missing+=("$tool")
      done
      if [ "${#missing[@]}" -gt 0 ]; then
        fail "full openSUSE image compile missing tools: ${missing[*]}"
      fi
      ;;
    *)
      fail "full openSUSE image compile requires Linux, or macOS with Docker"
      ;;
  esac
  rm -f "$full_image"
  run_logged "$full_log" \
    ./alpine-usb build \
      --distro opensuse \
      --release tumbleweed \
      --image-size "${LINUX_USB_FULL_IMAGE_SIZE:-8G}" \
      --output "$full_image" \
      --password testpass \
      --desktop none \
      --display-manager none \
      --no-wifi \
      --no-bluetooth \
      --audio none \
      --browser none \
      -y
  [ -s "$full_image" ] || fail "full openSUSE image build did not create a non-empty image at $full_image"
  assert_log_contains "$full_log" 'Image ready:|openSUSE rootfs populated' 'full openSUSE image build success marker'
fi

log "Image compile check passed. Logs: $WORK_DIR"
