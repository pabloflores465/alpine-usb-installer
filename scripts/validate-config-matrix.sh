#!/usr/bin/env bash
# Dry-run supported LEDIT configuration matrix across all distro backends.
# This validates option normalization, distro branch/release choices, package-list
# generation, and display-manager/session compatibility guards without creating images.
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

distros=(alpine arch debian fedora gentoo nixos opensuse rhel slackware ubuntu void)
if [ -n "${MATRIX_DISTROS:-}" ]; then
  # shellcheck disable=SC2206
  distros=(${MATRIX_DISTROS})
fi

if [ "${MATRIX_FULL:-0}" = "1" ]; then
  desktops=(xfce gnome plasma mate lxqt none)
  wm_profiles=("" "i3" "sway" "hyprland awesome bspwm openbox labwc")
  network_profiles=("1:1" "0:0") # wifi:bluetooth
  legacy_x11_profiles=(1 0)
  kernels=(lts stable)
else
  # Default path stays practical for local/pre-push checks while still touching
  # every distro. Set MATRIX_FULL=1 for the exhaustive desktop/WM/DM/kernel grid.
  desktops=(xfce plasma none)
  wm_profiles=("" "i3" "sway")
  network_profiles=("1:1" "0:0")
  legacy_x11_profiles=(1 0)
  kernels=(lts)
fi

branches_for() {
  case "$1" in
    alpine) printf '%s\n' latest-stable ;;
    arch) printf '%s\n' rolling ;;
    debian) printf '%s\n' stable ;;
    fedora) printf '%s\n' stable ;;
    gentoo) printf '%s\n' stable ;;
    nixos) printf '%s\n' nixos-24.11 ;;
    opensuse) printf '%s\n' tumbleweed ;;
    rhel) printf '%s\n' 9 ;;
    slackware) printf '%s\n' stable ;;
    ubuntu) printf '%s\n' 24.04 ;;
    void) printf '%s\n' current ;;
    *) return 1 ;;
  esac
}

all_branches_for() {
  case "$1" in
    alpine) printf '%s\n' latest-stable edge v3.22 v3.21 ;;
    arch) printf '%s\n' rolling stable ;;
    debian) printf '%s\n' stable testing sid trixie bookworm forky ;;
    fedora) printf '%s\n' stable latest rawhide 42 41 ;;
    gentoo) printf '%s\n' stable testing ;;
    nixos) printf '%s\n' nixos-24.11 nixos-25.05 nixos-unstable ;;
    opensuse) printf '%s\n' tumbleweed leap-16.0 leap-15.6 ;;
    rhel) printf '%s\n' 9 10 ;;
    slackware) printf '%s\n' stable current 15.0 ;;
    ubuntu) printf '%s\n' 24.04 noble 22.04 jammy ;;
    void) printf '%s\n' current glibc ;;
    *) return 1 ;;
  esac
}

bootloaders_for() {
  case "$1" in
    gentoo|rhel|slackware) printf '%s\n' grub ;;
    nixos) printf '%s\n' extlinux ;;
    *) printf '%s\n' grub systemd-boot ;;
  esac
}

display_managers_for() {
  distro="$1" desktop="$2" wms="$3"
  if [ "$distro" = rhel ]; then
    if [ "$desktop" = none ] && [ -z "$wms" ]; then printf '%s\n' auto none; return; fi
    printf '%s\n' auto lightdm sddm gdm none
    return
  fi
  if [ "$desktop" = none ] && [ -z "$wms" ]; then
    printf '%s\n' auto greetd none
    return
  fi
  case "$wms" in sway*|hyprland*|labwc*) printf '%s\n' auto sddm gdm greetd none ;; *) printf '%s\n' auto lightdm sddm gdm lxdm greetd none ;; esac
}

wm_profiles_for() {
  case "$1" in
    rhel) printf '%s\n' "" "i3" "sway" "openbox" ;;
    *) printf '%s\n' "${wm_profiles[@]}" ;;
  esac
}

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
  printf '%s|%s|%s|%s|%s|%s|%s|%s|%s|%s\0' "$@" >> "$cases_file"
}

for distro in "${distros[@]}"; do
  if [ "${MATRIX_BRANCHES:-default}" = all ]; then
    branches_cmd=all_branches_for
  else
    branches_cmd=branches_for
  fi
  while IFS= read -r branch; do
    for desktop in "${desktops[@]}"; do
      while IFS= read -r wms; do
        while IFS= read -r dm; do
          while IFS= read -r bootloader; do
            for kernel in "${kernels[@]}"; do
              for net in "${network_profiles[@]}"; do
                wifi="${net%%:*}"
                bluetooth="${net##*:}"
                for legacy_x11 in "${legacy_x11_profiles[@]}"; do
                  add_case "$distro" "$branch" "$desktop" "$wms" "$dm" "$bootloader" "$kernel" "$wifi" "$bluetooth" "$legacy_x11"
                done
              done
            done
          done < <(bootloaders_for "$distro")
        done < <(display_managers_for "$distro" "$desktop" "$wms")
      done < <(wm_profiles_for "$distro")
    done
  done < <($branches_cmd "$distro")
done

xargs -0 -n 1 -P "$jobs" bash -c '
  IFS="|" read -r distro branch desktop wms dm bootloader kernel wifi bluetooth legacy_x11 <<< "$1"
  out=$(mktemp)
  if ./ledit build \
    --distro "$distro" \
    --branch "$branch" \
    --dry-run \
    --password testpass \
    --desktop "$desktop" \
    --tiling-wms "$wms" \
    --display-manager "$dm" \
    --bootloader "$bootloader" \
    --kernel "$kernel" \
    $( [ "$wifi" = 1 ] && printf %s --wifi || printf %s --no-wifi ) \
    $( [ "$bluetooth" = 1 ] && printf %s --bluetooth || printf %s --no-bluetooth ) \
    $( [ "$legacy_x11" = 1 ] && printf %s --legacy-x11-drivers || printf %s --no-legacy-x11-drivers ) \
    -y >"$out" 2>&1; then
    printf ".\n" >> "$OK_FILE"
  else
    {
      printf "FAILED: distro=%s branch=%s desktop=%s wms=%s dm=%s bootloader=%s kernel=%s wifi=%s bluetooth=%s legacy_x11=%s\n" \
        "$distro" "$branch" "${desktop:-none}" "${wms:-none}" "$dm" "$bootloader" "$kernel" "$wifi" "$bluetooth" "$legacy_x11"
      tail -40 "$out"
    } >> "$FAIL_FILE"
    rm -f "$out"
    exit 1
  fi
  rm -f "$out"
' _ < "$cases_file" || true

ok="$(wc -l < "$OK_FILE" | tr -d ' ')"
failed="$(wc -l < "$FAIL_FILE" | tr -d ' ')"
if [ "$failed" -gt 0 ]; then
  cat "$FAIL_FILE" >&2
fi

echo "LEDIT dry-run matrix complete: ok=$ok failed=$failed jobs=$jobs distros=${distros[*]} branches=${MATRIX_BRANCHES:-default} full=${MATRIX_FULL:-0}"
[ "$failed" -eq 0 ]
