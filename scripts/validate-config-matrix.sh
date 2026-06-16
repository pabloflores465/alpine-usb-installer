#!/usr/bin/env bash
# Dry-run the supported configuration matrix without installing packages.
# This validates option normalization, package-list generation and the
# polkit/display-manager compatibility guards in configure-alpine-usb.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

default_jobs() {
  getconf _NPROCESSORS_ONLN 2>/dev/null \
    || sysctl -n hw.ncpu 2>/dev/null \
    || printf '4\n'
}

jobs="${JOBS:-$(default_jobs)}"
case "$jobs" in *[!0-9]*|"") jobs=4 ;; esac
[ "$jobs" -gt 0 ] || jobs=1

desktops=(xfce gnome plasma mate lxqt none)
display_managers=(auto lightdm sddm gdm lxdm greetd none)
bootloaders=(grub systemd-boot)
kernels=(lts stable)
wm_profiles=("" "i3" "sway" "hyprland awesome bspwm openbox labwc")
network_profiles=("1:1" "0:0") # wifi:bluetooth
legacy_x11_profiles=(1 0)

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
cases_file="$tmpdir/cases.bin"
OK_FILE="$tmpdir/ok"
FAIL_FILE="$tmpdir/fail"
: > "$cases_file"
: > "$OK_FILE"
: > "$FAIL_FILE"
export OK_FILE FAIL_FILE

add_case() {
  printf '%s|%s|%s|%s|%s|%s|%s|%s\0' "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" >> "$cases_file"
}

for desktop in "${desktops[@]}"; do
  for wms in "${wm_profiles[@]}"; do
    # No graphical session: only auto/none/greetd are valid.
    dms=("${display_managers[@]}")
    if [[ "$desktop" == none && -z "$wms" ]]; then
      dms=(auto greetd none)
    fi
    # LightDM/LXDM are X11 display managers; do not test them as the default
    # launcher for WM-only Wayland sessions.
    if [[ "$desktop" == none && ( "$wms" == sway* || "$wms" == hyprland* || "$wms" == labwc* ) ]]; then
      dms=(auto sddm gdm greetd none)
    fi
    for dm in "${dms[@]}"; do
      for bootloader in "${bootloaders[@]}"; do
        for kernel in "${kernels[@]}"; do
          for net in "${network_profiles[@]}"; do
            wifi="${net%%:*}"
            bluetooth="${net##*:}"
            for legacy_x11 in "${legacy_x11_profiles[@]}"; do
              add_case "$desktop" "$wms" "$dm" "$bootloader" "$kernel" "$wifi" "$bluetooth" "$legacy_x11"
            done
          done
        done
      done
    done
  done
done

xargs -0 -n 1 -P "$jobs" bash -c '
  IFS="|" read -r desktop wms dm bootloader kernel wifi bluetooth legacy_x11 <<< "$1"
  if ALPINE_USB_DRY_RUN=1 \
    ALPINE_USB_DESKTOP="$desktop" \
    ALPINE_USB_TILING_WMS="$wms" \
    ALPINE_USB_DISPLAY_MANAGER="$dm" \
    ALPINE_USB_BOOTLOADER="$bootloader" \
    ALPINE_USB_KERNEL_FLAVOR="$kernel" \
    ALPINE_USB_WIFI="$wifi" \
    ALPINE_USB_BLUETOOTH="$bluetooth" \
    ALPINE_USB_LEGACY_X11_DRIVERS="$legacy_x11" \
    ./configure-alpine-usb.sh >/dev/null; then
    printf ".\n" >> "$OK_FILE"
  else
    printf "FAILED: desktop=%s wms=%s dm=%s bootloader=%s kernel=%s wifi=%s bluetooth=%s legacy_x11=%s\n" \
      "$desktop" "${wms:-none}" "$dm" "$bootloader" "$kernel" "$wifi" "$bluetooth" "$legacy_x11" >> "$FAIL_FILE"
    exit 1
  fi
' _ < "$cases_file" || true

ok="$(wc -l < "$OK_FILE" | tr -d ' ')"
failed="$(wc -l < "$FAIL_FILE" | tr -d ' ')"
if [ "$failed" -gt 0 ]; then
  cat "$FAIL_FILE" >&2
fi

echo "Dry-run matrix complete: ok=$ok failed=$failed jobs=$jobs"
[ "$failed" -eq 0 ]
