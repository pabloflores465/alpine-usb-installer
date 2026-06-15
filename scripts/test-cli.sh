#!/usr/bin/env bash
# Smoke-test the standalone CLI without building/flashing a real image.
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m py_compile cli.py tui.py gui.py
./tui.py --self-test >/dev/null
if [ "${SKIP_TUI_PTY_TESTS:-0}" != "1" ]; then
  python3 - <<'PY'
import os, pty, select, subprocess, time
master, slave = pty.openpty()
env = os.environ.copy()
env.setdefault("TERM", "xterm-256color")
proc = subprocess.Popen(["./tui.py"], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
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
./cli.py --help >/dev/null
./cli.py build --help >/dev/null
./cli.py build --dry-run --desktop xfce --bootloader systemd-boot --no-bluetooth --extra-package neovim -y >/tmp/alpine-usb-cli-dry-run.out
grep -q 'DRY RUN OK' /tmp/alpine-usb-cli-dry-run.out
grep -q 'neovim' /tmp/alpine-usb-cli-dry-run.out

if [ "${SKIP_NETWORK_TESTS:-0}" != "1" ]; then
  ./cli.py search firefox --limit 3 >/tmp/alpine-usb-cli-search.out
  grep -q 'firefox' /tmp/alpine-usb-cli-search.out
fi

echo "CLI smoke tests passed."
