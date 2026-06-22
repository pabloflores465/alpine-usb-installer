#!/usr/bin/env bash
# Compile Python and smoke dry-run every LEDIT distro backend without creating images.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m compileall -q alpine_usb

run_dry() {
  distro="$1"
  bootloader="$2"
  out="/tmp/ledit-check-${distro}.out"
  ./ledit build \
    --distro "$distro" \
    --dry-run \
    --password testpass \
    --profile minimal \
    --desktop none \
    --display-manager none \
    --bootloader "$bootloader" \
    -y >"$out"
  grep -Eq 'DRY RUN OK|dry-run OK|Dry-run OK|USB dry-run|configuration dry-run|configuration plan|configuration rendered successfully|Arch dry-run OK' "$out"
}

run_dry alpine grub
run_dry arch grub
run_dry debian grub
run_dry fedora grub
run_dry gentoo grub
run_dry nixos extlinux
run_dry opensuse grub
run_dry rhel grub
run_dry slackware grub
run_dry ubuntu grub
run_dry void grub

echo "LEDIT image compile dry-run checks passed."
