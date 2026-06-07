#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .qtvenv/bin/python ]; then
  python3 -m venv .qtvenv
  .qtvenv/bin/python -m pip install --upgrade pip
  .qtvenv/bin/python -m pip install PySide6
fi

exec .qtvenv/bin/python usb_qt.py
