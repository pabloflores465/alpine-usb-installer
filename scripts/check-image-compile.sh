#!/usr/bin/env bash
# Compile image configuration into concrete Fedora/Alpine build plans.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK_DIR=".work/image-compile"
FEDORA_LOG="$WORK_DIR/fedora.log"
ALPINE_LOG="$WORK_DIR/alpine.log"
mkdir -p "$WORK_DIR"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

assert_grep() {
  local pattern="$1" file="$2" message="$3"
  if ! grep -Eq "$pattern" "$file"; then
    printf 'ERROR: %s\n' "$message" >&2
    printf 'Last lines from %s:\n' "$file" >&2
    tail -n 40 "$file" >&2 || true
    exit 1
  fi
}

assert_non_empty_plan() {
  local file="$1"
  local selected
  selected="$(sed -nE 's/.*packages: ([0-9]+) selected.*/\1/p' "$file" | tail -n 1)"
  if [[ -z "$selected" || "$selected" == "0" ]]; then
    die "Fedora dry-run did not produce a non-empty package plan in $file"
  fi
  assert_grep '^Package list: .*[A-Za-z0-9]' "$file" "Fedora dry-run did not print a package list"
}

log "Compiling Python package tree..."
python3 -m compileall alpine_usb

log "Checking shell syntax..."
shell_scripts=(
  build-alpine-usb.sh
  configure-alpine-usb.sh
  build-fedora-usb.sh
)
while IFS= read -r script; do
  [[ -n "$script" ]] && shell_scripts+=("$script")
done < <(find . -maxdepth 2 -type f \( -name 'configure-fedora-usb.sh' -o -name '*fedora*configure*.sh' \) | sort)

seen=" "
for script in "${shell_scripts[@]}"; do
  script="${script#./}"
  [[ -f "$script" ]] || continue
  if [[ "$seen" == *" $script "* ]]; then
    continue
  fi
  seen+="$script "
  bash -n "$script"
done

log "Running Fedora dry-run through CLI..."
./alpine-usb build --distro fedora --release latest --dry-run --password testpass --desktop xfce -y >"$FEDORA_LOG" 2>&1
assert_grep 'Dry-run OK: Fedora configuration is valid\.' "$FEDORA_LOG" "Fedora dry-run success marker missing"
assert_non_empty_plan "$FEDORA_LOG"

log "Running Alpine minimal dry-run through CLI..."
./alpine-usb build --dry-run --password testpass --profile minimal -y >"$ALPINE_LOG" 2>&1
assert_grep '^DRY RUN OK$' "$ALPINE_LOG" "Alpine dry-run success marker missing"
assert_grep 'desktop=none' "$ALPINE_LOG" "Alpine minimal no-desktop plan missing"
assert_grep '^ packages: .*[A-Za-z0-9]' "$ALPINE_LOG" "Alpine dry-run did not print a package plan"

run_full_image_compile() {
  local output="$WORK_DIR/fedora-usb.img"
  local full_log="$WORK_DIR/fedora-full-build.log"
  case "$(uname -s)" in
    Darwin)
      if ! command -v docker >/dev/null 2>&1; then
        log "SKIP: full Fedora image compile requires Docker on macOS."
        return 0
      fi
      if ! docker info >/dev/null 2>&1; then
        log "SKIP: full Fedora image compile requires Docker Desktop to be running on macOS."
        return 0
      fi
      ;;
    Linux)
      if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
        log "SKIP: full Fedora image compile requires root on Linux for loop devices and filesystems."
        return 0
      fi
      local required=(dnf parted mkfs.vfat mkfs.ext4 losetup mount rsync grub2-install grub2-mkconfig)
      local missing=()
      for tool in "${required[@]}"; do
        command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
      done
      if [[ "${#missing[@]}" -gt 0 ]]; then
        log "SKIP: full Fedora image compile missing host tools: ${missing[*]}"
        return 0
      fi
      ;;
    *)
      log "SKIP: full Fedora image compile requires Linux or macOS with Docker."
      return 0
      ;;
  esac

  log "Running full Fedora image compile to $output..."
  ./alpine-usb build \
    --distro fedora \
    --release latest \
    --password testpass \
    --desktop xfce \
    --output "$output" \
    -y >"$full_log" 2>&1
  [[ -s "$output" ]] || die "Full Fedora image compile did not create $output; see $full_log"
}

if [[ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" == "1" ]]; then
  run_full_image_compile
else
  log "Full image compile skipped (set LINUX_USB_FULL_IMAGE_COMPILE=1 to enable)."
fi

log "Image compile check passed. Logs: $FEDORA_LOG $ALPINE_LOG"
