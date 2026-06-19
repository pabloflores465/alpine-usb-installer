#!/usr/bin/env bash
# Validate that supported image configuration compiles into concrete build plans.
# Default mode is host-safe: no root, Docker, loop devices, or full image build.
set -euo pipefail
cd "$(dirname "$0")/.."

work_dir=".work/image-compile"
mkdir -p "$work_dir"

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
need_file_nonempty() { [ -s "$1" ] || die "expected non-empty artifact: $1"; }

log "Compiling Python package"
python3 -m compileall alpine_usb

log "Checking shell syntax"
bash -n \
  build-alpine-usb.sh \
  configure-alpine-usb.sh \
  build-arch-usb.sh \
  configure-arch-usb.sh

arch_log="$work_dir/arch.log"
arch_packages="$work_dir/arch-packages.txt"
arch_config="$work_dir/arch-config.env"
rm -f "$arch_log" "$arch_packages" "$arch_config"

log "Compiling Arch dry-run build plan through CLI"
ARCH_USB_PACKAGES_FILE="$arch_packages" \
ARCH_USB_CONFIG_FILE="$arch_config" \
  ./alpine-usb build \
    --distro arch \
    --dry-run \
    --password testpass \
    --desktop none \
    --no-bluetooth \
    --no-wifi \
    --extra-package neovim \
    -y >"$arch_log" 2>&1

grep -q 'Arch dry-run OK' "$arch_log" || die "Arch dry-run did not report success; see $arch_log"
need_file_nonempty "$arch_packages"
need_file_nonempty "$arch_config"
grep -q '^neovim$' "$arch_packages" || die "Arch package plan missing extra package neovim"
grep -q '^ARCH_USB_BRANCH=rolling$' "$arch_config" || die "Arch config artifact missing Arch branch selection"

alpine_log="$work_dir/alpine.log"
alpine_plan="$work_dir/alpine-packages.txt"
rm -f "$alpine_log" "$alpine_plan"

log "Compiling Alpine dry-run build plan through CLI"
./alpine-usb build \
  --dry-run \
  --password testpass \
  --profile minimal \
  --desktop none \
  --no-bluetooth \
  --no-wifi \
  -y >"$alpine_log" 2>&1

grep -q 'DRY RUN OK' "$alpine_log" || die "Alpine dry-run did not report success; see $alpine_log"
awk '/^ packages:/{sub(/^ packages:[[:space:]]*/, ""); gsub(/[[:space:]]+/, "\n"); print}' "$alpine_log" > "$alpine_plan"
need_file_nonempty "$alpine_plan"
grep -q '^alpine-base$' "$alpine_plan" || die "Alpine package plan missing alpine-base"

run_full_image_compile() {
  full_log="$work_dir/arch-full.log"
  full_image="$PWD/$work_dir/arch-full.img"
  rm -f "$full_log" "$full_image"

  case "$(uname -s)" in
    Darwin)
      command -v docker >/dev/null 2>&1 || die "Full Arch image compile on macOS requires Docker"
      docker info >/dev/null 2>&1 || die "Docker is not running; start Docker Desktop for full Arch image compile"
      ;;
    Linux)
      if [ "$(id -u)" != "0" ]; then
        die "Full Arch image compile requires root on Linux for image/loop setup"
      fi
      for tool in python3 pacstrap arch-chroot sfdisk losetup mkfs.fat mkfs.ext4 mount umount; do
        command -v "$tool" >/dev/null 2>&1 || die "Full Arch image compile missing $tool"
      done
      ;;
    *)
      die "Full Arch image compile unsupported host $(uname -s)"
      ;;
  esac

  log "Running gated full Arch image compile"
  ./alpine-usb build \
    --distro arch \
    --output "$full_image" \
    --password testpass \
    --profile minimal \
    --desktop none \
    --display-manager none \
    --no-bluetooth \
    --no-wifi \
    --audio none \
    --browser none \
    --firmware none \
    --image-size "${LINUX_USB_FULL_IMAGE_SIZE:-8G}" \
    -y >"$full_log" 2>&1
  need_file_nonempty "$full_image"
}

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  run_full_image_compile
else
  log "Skipping full image compile (set LINUX_USB_FULL_IMAGE_COMPILE=1 to enable)"
fi

log "Image compile check passed. Logs/artifacts: $work_dir"
