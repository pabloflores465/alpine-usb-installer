#!/usr/bin/env bash
# Validate that Alpine and NixOS image configurations compile into concrete build plans.
set -euo pipefail
cd "$(dirname "$0")/.."

work_dir=".work/image-compile"
mkdir -p "$work_dir"

log() {
  printf '==> %s\n' "$*"
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_in_file() {
  local needle="$1"
  local file="$2"
  if ! grep -Fq "$needle" "$file"; then
    fail "Expected '$needle' in $file"
  fi
}

log "Compiling Python package modules"
python3 -m compileall alpine_usb

log "Checking shell script syntax"
shell_scripts=(build-alpine-usb.sh configure-alpine-usb.sh scripts/check-image-compile.sh)
for script in "${shell_scripts[@]}"; do
  if [ -f "$script" ]; then
    bash -n "$script"
  fi
done

nixos_log="$work_dir/nixos.log"
alpine_log="$work_dir/alpine.log"

log "Rendering NixOS build plan through CLI dry-run"
./alpine-usb build \
  --distro nixos \
  --dry-run \
  --password testpass \
  --desktop xfce \
  --bootloader systemd-boot \
  --extra-package htop \
  -y >"$nixos_log" 2>&1

require_in_file "NixOS configuration rendered successfully" "$nixos_log"
require_in_file "flake.nix" "$nixos_log"
require_in_file "configuration.nix" "$nixos_log"
require_in_file "nixosConfigurations.usb" "$nixos_log"
require_in_file "boot.loader.systemd-boot.enable = lib.mkForce true;" "$nixos_log"
require_in_file "services.xserver.desktopManager.xfce.enable = true;" "$nixos_log"
require_in_file "environment.systemPackages = with pkgs; [ pkgs.htop" "$nixos_log"
if ! awk '/configuration\.nix/{seen=1; next} seen && /system\.stateVersion =/{found=1} END{exit found ? 0 : 1}' "$nixos_log"; then
  fail "NixOS dry-run did not include a non-empty generated configuration in $nixos_log"
fi

log "Rendering Alpine no-desktop build plan through CLI dry-run"
./alpine-usb build \
  --dry-run \
  --password testpass \
  --profile minimal \
  -y >"$alpine_log" 2>&1

require_in_file "DRY RUN OK" "$alpine_log"
require_in_file "desktop=none" "$alpine_log"
require_in_file "display_manager=none" "$alpine_log"

if [ "${LINUX_USB_FULL_IMAGE_COMPILE:-0}" = "1" ]; then
  log "Running gated full NixOS image compile"
  if ! command -v nixos-generate >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
    fail "LINUX_USB_FULL_IMAGE_COMPILE=1 requested but neither nixos-generate nor Docker is on PATH"
  fi
  ./alpine-usb build \
    --distro nixos \
    --profile minimal \
    --password testpass \
    --desktop none \
    --display-manager none \
    --network none \
    --no-wifi \
    --no-bluetooth \
    --audio none \
    --browser none \
    --firmware none \
    --bootloader extlinux \
    --output "$work_dir/nixos-full.img" \
    -y >"$work_dir/nixos-full.log" 2>&1
  require_in_file "NixOS image written" "$work_dir/nixos-full.log"
else
  log "Skipping full NixOS image build (set LINUX_USB_FULL_IMAGE_COMPILE=1 to enable)"
fi

log "Image compile check passed. Logs: $nixos_log $alpine_log"
