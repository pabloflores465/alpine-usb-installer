#!/usr/bin/env bash
set -euo pipefail
export TK_SILENCE_DEPRECATION=1
cd "$(dirname "$0")"

# Prefer local venv created from macOS system Python because Nix/Homebrew Python
# may not include Tkinter (_tkinter).
if [ ! -x .venv/bin/python ]; then
  /usr/bin/python3 -m venv .venv
fi

exec .venv/bin/python usb_gui.py
