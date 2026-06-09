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
  "gnome:ALPINE_USB_DESKTOP=gnome"
  "plasma-systemd-stable:ALPINE_USB_DESKTOP=plasma ALPINE_USB_BOOTLOADER=systemd-boot ALPINE_USB_KERNEL_FLAVOR=stable"
  "mate:ALPINE_USB_DESKTOP=mate"
  "lxqt:ALPINE_USB_DESKTOP=lxqt"
  "wm-greetd:ALPINE_USB_DESKTOP=none ALPINE_USB_TILING_WMS=i3,sway ALPINE_USB_DISPLAY_MANAGER=greetd"
)

for item in "${profiles[@]}"; do
  name="${item%%:*}"
  envs="${item#*:}"
  echo "--- apk solver: $name ---"
  packages=$(
    # shellcheck disable=SC2086 # envs is a controlled list of VAR=value assignments.
    env ALPINE_USB_DRY_RUN=1 $envs ./configure-alpine-usb.sh \
      | awk -F'packages:' '/packages:/{print $2}'
  )
  [ -n "$packages" ] || { echo "No packages generated for $name" >&2; exit 1; }
  docker run --rm --platform linux/amd64 alpine:latest sh -c \
    "apk update >/dev/null && apk add -s $packages >/tmp/apk.out && tail -1 /tmp/apk.out"
done

echo "APK solver checks passed."
