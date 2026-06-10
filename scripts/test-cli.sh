#!/usr/bin/env bash
# Smoke-test the standalone CLI without building/flashing a real image.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m py_compile alpine_usb_cli.py alpine_usb_tui.py
./run_tui.sh --self-test >/dev/null
./run_cli.sh --help >/dev/null
./run_cli.sh build --help >/dev/null
./run_cli.sh build --dry-run --desktop xfce --bootloader systemd-boot --no-bluetooth --extra-package neovim -y >/tmp/alpine-usb-cli-dry-run.out
grep -q 'DRY RUN OK' /tmp/alpine-usb-cli-dry-run.out
grep -q 'neovim' /tmp/alpine-usb-cli-dry-run.out

if [ "${SKIP_NETWORK_TESTS:-0}" != "1" ]; then
  ./run_cli.sh search firefox --limit 3 >/tmp/alpine-usb-cli-search.out
  grep -q 'firefox' /tmp/alpine-usb-cli-search.out
fi

echo "CLI smoke tests passed."
