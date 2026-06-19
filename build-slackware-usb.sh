#!/bin/sh
# Build a bootable Slackware USB installer artifact.
#
# The custom installed-rootfs builder is still future work. For gated full image
# compile, this script validates the Slackware package plan, downloads the
# official Slackware usbboot.img, verifies CHECKSUMS.md5, and writes that real
# bootable USB image to the requested output path.
set -eu

log() {
  printf '[slackware-build] %s\n' "$*"
}

fail() {
  printf '[slackware-build] ERROR: %s\n' "$*" >&2
  exit 1
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || fail "Required tool not found: $1"
}

md5_file() {
  if command -v md5sum >/dev/null 2>&1; then
    md5sum "$1" | awk '{print $1}'
  elif command -v md5 >/dev/null 2>&1; then
    md5 -q "$1"
  else
    fail "Required tool not found: md5sum or md5"
  fi
}

release_path() {
  case "$1" in
    stable) printf 'slackware64-15.0' ;;
    current) printf 'slackware64-current' ;;
    [0-9]*.[0-9]*) printf 'slackware64-%s' "$1" ;;
    *) fail "Unsupported Slackware release: $1" ;;
  esac
}

require_tool awk
require_tool curl

ARCH_VALUE=${ARCH:-x86_64}
case "$ARCH_VALUE" in
  x86_64) ;;
  *) fail "Slackware full image fallback currently supports x86_64 only (got: $ARCH_VALUE)" ;;
esac

RELEASE=${SLACKWARE_RELEASE:-stable}
TREE=$(release_path "$RELEASE")
BASE_URL=${SLACKWARE_MIRROR_BASE_URL:-https://mirrors.slackware.com/slackware/$TREE}
IMAGE_REL=usb-and-pxe-installers/usbboot.img
CHECKSUM_REL=./$IMAGE_REL
OUTPUT=${OUTPUT_PATH:-${IMAGE_NAME:-slackware-full.img}}
WORK_DIR=${SLACKWARE_USBBOOT_CACHE_DIR:-.work/slackware-usbboot}
IMAGE_PATH=$WORK_DIR/$TREE-usbboot.img
CHECKSUMS_PATH=$WORK_DIR/$TREE-CHECKSUMS.md5

mkdir -p "$WORK_DIR"

log "Validating Slackware build plan"
ALPINE_USB_DRY_RUN=1 ./configure-slackware-usb.sh

if [ ! -s "$IMAGE_PATH" ]; then
  log "Downloading $BASE_URL/$IMAGE_REL"
  curl -fsSL --retry 3 -C - "$BASE_URL/$IMAGE_REL" -o "$IMAGE_PATH"
else
  log "Reusing cached USB image $IMAGE_PATH"
fi

log "Fetching and verifying MD5 checksum"
curl -fsSL --retry 3 "$BASE_URL/CHECKSUMS.md5" -o "$CHECKSUMS_PATH"
EXPECTED=$(awk -v name="$CHECKSUM_REL" 'length($1) == 32 && $2 == name {print $1; exit}' "$CHECKSUMS_PATH")
[ -n "$EXPECTED" ] || fail "Could not find checksum for $CHECKSUM_REL in $CHECKSUMS_PATH"
ACTUAL=$(md5_file "$IMAGE_PATH")
if [ "$ACTUAL" != "$EXPECTED" ]; then
  rm -f "$IMAGE_PATH"
  fail "MD5 mismatch for $IMAGE_REL"
fi

mkdir -p "$(dirname "$OUTPUT")"
TMP_OUTPUT=$OUTPUT.tmp
rm -f "$TMP_OUTPUT"
log "Writing Slackware bootable USB image to $OUTPUT"
cp "$IMAGE_PATH" "$TMP_OUTPUT"
mv "$TMP_OUTPUT" "$OUTPUT"
log "Slackware image written: $OUTPUT"
