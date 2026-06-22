#!/usr/bin/env bash
# Full local project check: compile, lint, tests, shell syntax, and smoke-run entrypoints.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m py_compile ledit alpine-usb gui.py cli.py tui.py apk_index.py $(find alpine_usb -name '*.py' -type f | sort)
ruff check .
ruff format --check .
pytest
bash -n \
  build-*-usb.sh \
  configure-*-usb.sh \
  scripts/build-macos-dmg.sh \
  scripts/package-release-assets.sh \
  scripts/check-apk-solver.sh \
  scripts/check-image-compile.sh \
  scripts/test-cli.sh \
  scripts/validate-config-matrix.sh

./ledit --help >/dev/null
./alpine-usb --help >/dev/null
./ledit distros >/dev/null
./ledit tui --self-test >/dev/null
./ledit build --dry-run --password testpass --profile minimal -y >/tmp/ledit-check-minimal.out
grep -q 'DRY RUN OK' /tmp/ledit-check-minimal.out
grep -q 'desktop=none' /tmp/ledit-check-minimal.out

if [ "${SKIP_IMAGE_COMPILE_CHECK:-0}" != "1" ]; then
  scripts/check-image-compile.sh
fi

if [ "${SKIP_NETWORK_TESTS:-0}" != "1" ]; then
  ./ledit search firefox --limit 3 >/tmp/ledit-check-search.out
  grep -q 'firefox' /tmp/ledit-check-search.out
fi

echo "Project check passed."
