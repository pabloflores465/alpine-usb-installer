#!/usr/bin/env bash
# Dry-run the supported configuration matrix without installing packages.
# This validates option normalization, package-list generation and the
# polkit/display-manager compatibility guards in configure-alpine-usb.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

desktops=(xfce gnome plasma mate lxqt none)
display_managers=(auto lightdm sddm gdm lxdm greetd none)
bootloaders=(grub systemd-boot)
kernels=(lts stable)
wm_profiles=("" "i3" "sway" "hyprland awesome bspwm openbox labwc")
network_profiles=("1:1" "0:0") # wifi:bluetooth

ok=0
failed=0

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
            if ALPINE_USB_DRY_RUN=1 \
              ALPINE_USB_DESKTOP="$desktop" \
              ALPINE_USB_TILING_WMS="$wms" \
              ALPINE_USB_DISPLAY_MANAGER="$dm" \
              ALPINE_USB_BOOTLOADER="$bootloader" \
              ALPINE_USB_KERNEL_FLAVOR="$kernel" \
              ALPINE_USB_WIFI="$wifi" \
              ALPINE_USB_BLUETOOTH="$bluetooth" \
              ./configure-alpine-usb.sh >/dev/null; then
              ok=$((ok + 1))
            else
              echo "FAILED: desktop=$desktop wms='${wms:-none}' dm=$dm bootloader=$bootloader kernel=$kernel wifi=$wifi bluetooth=$bluetooth" >&2
              failed=$((failed + 1))
            fi
          done
        done
      done
    done
  done
done

echo "Dry-run matrix complete: ok=$ok failed=$failed"
[ "$failed" -eq 0 ]
