#!/usr/bin/env bash
# Validate that image options compile into concrete Alpine and RHEL-family build plans.
set -euo pipefail
cd "$(dirname "$0")/.."

work_dir=".work/image-compile"
mkdir -p "$work_dir"

log() { printf '[image-compile] %s\n' "$*"; }
fail() { printf '[image-compile] ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

assert_log_contains() {
  local file="$1"
  local pattern="$2"
  grep -q -- "$pattern" "$file" || fail "Expected '$pattern' in $file"
}

assert_non_empty_rhel_plan() {
  local file="$1"
  local packages
  packages="$(awk -F= '/^packages=/{print $2; exit}' "$file")"
  [ -n "$packages" ] || fail "RHEL dry-run did not produce a non-empty package plan in $file"
}

assert_non_empty_alpine_plan() {
  local file="$1"
  local packages
  packages="$(awk -F'packages:' '/^ packages:/{print $2; exit}' "$file")"
  [ -n "$packages" ] || fail "Alpine dry-run did not produce a non-empty package plan in $file"
}

run_full_image_compile_if_requested() {
  [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ] || return 0

  log "Full image compile requested."
  if [ "$(uname -s)" != "Linux" ]; then
    log "SKIP: full RHEL-family image compile requires a Linux host."
    return 0
  fi
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    log "SKIP: full RHEL-family image compile requires root for loop devices and mounts."
    return 0
  fi
  for tool in dnf parted mkfs.vfat mkfs.xfs mount umount grub2-install losetup blkid; do
    have "$tool" || fail "Full image compile requested, but required tool is missing: $tool"
  done

  local full_log="$work_dir/rhel-full.log"
  local output
  output="$(pwd)/$work_dir/rocky-full.img"
  rm -f "$output"
  log "Running full Rocky image build to $output (log: $full_log)"
  ./alpine-usb build \
    --distro rocky \
    --release 9 \
    --password testpass \
    --desktop none \
    --display-manager none \
    --browser none \
    --audio none \
    --no-wifi \
    --no-bluetooth \
    --output "$output" \
    -y 2>&1 | tee "$full_log"
  [ -s "$output" ] || fail "Full image compile did not create a non-empty image: $output"
}

log "Compiling Python package tree."
python3 -m compileall alpine_usb

log "Checking shell syntax for build/config scripts."
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-rhel-usb.sh \
  configure-rhel-usb.sh

rhel_log="$work_dir/rhel.log"
log "Running Rocky/RHEL-family CLI dry-run (log: $rhel_log)."
./alpine-usb build \
  --distro rocky \
  --release 9 \
  --dry-run \
  --password testpass \
  --desktop xfce \
  --wm i3 \
  --no-bluetooth \
  --extra-package vim-enhanced \
  -y 2>&1 | tee "$rhel_log"
assert_log_contains "$rhel_log" 'RHEL-family dry-run OK'
assert_non_empty_rhel_plan "$rhel_log"

alpine_log="$work_dir/alpine.log"
log "Running Alpine minimal no-desktop CLI dry-run (log: $alpine_log)."
./alpine-usb build \
  --dry-run \
  --password testpass \
  --profile minimal \
  --desktop none \
  --display-manager none \
  --browser none \
  --audio none \
  --no-wifi \
  --no-bluetooth \
  -y 2>&1 | tee "$alpine_log"
assert_log_contains "$alpine_log" 'DRY RUN OK'
assert_non_empty_alpine_plan "$alpine_log"

run_full_image_compile_if_requested

log "Image configuration compile check passed."
