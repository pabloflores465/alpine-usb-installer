#!/bin/sh
# Placeholder builder entry for Slackware. The CLI routes Slackware dry-run validation
# to configure-slackware-usb.sh; full raw-image assembly still needs the mirror/chroot
# build implementation documented in README.
set -eu
ALPINE_USB_DRY_RUN="${ALPINE_USB_DRY_RUN:-0}" ./configure-slackware-usb.sh
