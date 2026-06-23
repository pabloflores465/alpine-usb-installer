#!/usr/bin/env bash
# Smoke-test the unified terminal entrypoint without building/flashing a real image.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m py_compile ledit cli.py tui.py gui.py apk_index.py $(find ledit_core -name '*.py' -type f | sort)
./ledit tui --self-test >/dev/null
if [ "${SKIP_TUI_PTY_TESTS:-0}" != "1" ]; then
  python3 - <<'PY'
import os, pty, select, subprocess, time
master, slave = pty.openpty()
env = os.environ.copy()
env.setdefault("TERM", "xterm-256color")
proc = subprocess.Popen(["./ledit"], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
os.close(slave)
time.sleep(0.5)
os.write(master, b"q")
time.sleep(0.1)
os.write(master, b"y")
end = time.time() + 5
while time.time() < end and proc.poll() is None:
    r, _, _ = select.select([master], [], [], 0.2)
    if r:
        try:
            os.read(master, 4096)
        except OSError:
            break
code = proc.wait(timeout=5)
os.close(master)
raise SystemExit(code)
PY
fi
./ledit --help >/dev/null
./ledit build --help >/dev/null
./ledit distros >/dev/null
./ledit build --dry-run --password testpass --desktop xfce --bootloader systemd-boot --no-bluetooth --extra-package neovim -y >/tmp/ledit-cli-dry-run.out
grep -q 'DRY RUN OK' /tmp/ledit-cli-dry-run.out
grep -q 'neovim' /tmp/ledit-cli-dry-run.out
./ledit build --dry-run --password testpass --profile minimal -y >/tmp/ledit-cli-minimal.out
grep -q 'desktop=none' /tmp/ledit-cli-minimal.out
grep -q 'legacy_x11_drivers=0' /tmp/ledit-cli-minimal.out
scripts/check-image-compile.sh

if [ "${SKIP_NETWORK_TESTS:-0}" != "1" ]; then
  ./ledit search firefox --limit 3 >/tmp/ledit-cli-search.out
  grep -q 'firefox' /tmp/ledit-cli-search.out
fi

echo "Unified terminal smoke tests passed."
