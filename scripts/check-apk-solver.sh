#!/usr/bin/env bash
# Verify representative profiles with Alpine's real apk dependency solver.
# This catches package conflicts that dry-run validation cannot see (for example
# bluez-obexd vs obexd-enhanced in GNOME Bluetooth stacks).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for apk solver checks." >&2
  exit 1
fi

profiles=(
  "default:"
  "gnome:LEDIT_USB_DESKTOP=gnome"
  "plasma-systemd-stable:LEDIT_USB_DESKTOP=plasma LEDIT_USB_BOOTLOADER=systemd-boot LEDIT_USB_KERNEL_FLAVOR=stable"
  "mate:LEDIT_USB_DESKTOP=mate"
  "lxqt:LEDIT_USB_DESKTOP=lxqt"
  "wm-greetd:LEDIT_USB_DESKTOP=none LEDIT_USB_TILING_WMS=i3,sway LEDIT_USB_DISPLAY_MANAGER=greetd"
  "minimal:LEDIT_USB_DESKTOP=none LEDIT_USB_DISPLAY_MANAGER=none LEDIT_USB_WIFI=0 LEDIT_USB_BLUETOOTH=0 LEDIT_USB_AUDIO=none LEDIT_USB_BROWSER=none LEDIT_USB_FIRMWARE=none LEDIT_USB_LEGACY_X11_DRIVERS=0"
)

tmpdir="$PWD/.work/apk-solver-$$"
rm -rf "$tmpdir"
mkdir -p "$tmpdir"
trap 'rm -rf "$tmpdir"' EXIT
packages_file="$tmpdir/packages.tsv"
: > "$packages_file"

for item in "${profiles[@]}"; do
  name="${item%%:*}"
  envs="${item#*:}"
  packages=$(
    # shellcheck disable=SC2086 # envs is a controlled list of VAR=value assignments.
    env LEDIT_USB_DRY_RUN=1 $envs ./configure-alpine-usb.sh \
      | awk -F'packages:' '/packages:/{print $2}'
  )
  [ -n "$packages" ] || { echo "No packages generated for $name" >&2; exit 1; }
  printf '%s\t%s\n' "$name" "$packages" >> "$packages_file"
done

docker run --rm --platform linux/amd64 -v "$tmpdir:/cases:ro" alpine:latest sh -ceu '
  apk update >/dev/null
  while IFS="$(printf "\t")" read -r name packages; do
    [ -n "$name" ] || continue
    echo "--- apk solver: $name ---"
    # shellcheck disable=SC2086 # packages are generated APK identifiers.
    apk add -s $packages >/tmp/apk.out
    tail -1 /tmp/apk.out
  done < /cases/packages.tsv
'

echo "APK solver checks passed."
