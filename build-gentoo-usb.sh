#!/bin/sh
set -eu
cat >&2 <<'MSG'
ERROR: Gentoo full image build is not implemented in this branch yet.
The Gentoo backend currently supports CLI/GUI/TUI discovery, package mapping/search,
and dry-run validation against a stage3/OpenRC plan. Use:
  ./alpine-usb build --distro gentoo --branch stable --dry-run --password ...
See docs/gentoo.md for implemented scope and remaining build steps.
MSG
exit 2
