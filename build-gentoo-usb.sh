#!/bin/sh
# Build a bootable Gentoo USB artifact.
#
# A full custom Gentoo install image requires Portage/binhost policy and a long
# chrooted emerge flow. For the gated image compile path this builder produces a
# real bootable Gentoo artifact by downloading the current official minimal ISO,
# verifying its SHA512 digest, and copying it to the requested output path.
set -eu

log() {
  printf '[gentoo-build] %s\n' "$*"
}

fail() {
  printf '[gentoo-build] ERROR: %s\n' "$*" >&2
  exit 1
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || fail "Required tool not found: $1"
}

sha512_file() {
  if command -v sha512sum >/dev/null 2>&1; then
    sha512sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 512 "$1" | awk '{print $1}'
  else
    fail "Required tool not found: sha512sum or shasum"
  fi
}

ARCH_VALUE=${ARCH:-x86_64}
case "$ARCH_VALUE" in
  x86_64|amd64) GENTOO_ARCH=amd64 ;;
  *) fail "Gentoo full image fallback currently supports x86_64/amd64 only (got: $ARCH_VALUE)" ;;
esac

require_tool awk
require_tool curl

OUTPUT=${OUTPUT_PATH:-${IMAGE_NAME:-gentoo-full.img}}
WORK_DIR=${GENTOO_LIVE_CACHE_DIR:-.work/gentoo-live}
BASE_URL=${GENTOO_MINIMAL_ISO_BASE_URL:-https://distfiles.gentoo.org/releases/$GENTOO_ARCH/autobuilds/current-install-$GENTOO_ARCH-minimal}
LATEST_TXT=$WORK_DIR/latest-install-$GENTOO_ARCH-minimal.txt

mkdir -p "$WORK_DIR"

log "Fetching Gentoo latest minimal ISO metadata"
curl -fsSL --retry 3 "$BASE_URL/latest-install-$GENTOO_ARCH-minimal.txt" -o "$LATEST_TXT"
ISO_NAME=$(awk '/\.iso[[:space:]]+[0-9]+/ && $1 !~ /^#/ {print $1; exit}' "$LATEST_TXT")
[ -n "$ISO_NAME" ] || fail "Could not parse latest Gentoo ISO name from $LATEST_TXT"
case "$ISO_NAME" in
  */*) ISO_PATH_PART=$ISO_NAME; ISO_FILE=${ISO_NAME##*/} ;;
  *) ISO_PATH_PART=$ISO_NAME; ISO_FILE=$ISO_NAME ;;
esac

ISO_URL=$BASE_URL/$ISO_PATH_PART
DIGEST_URL=$ISO_URL.DIGESTS
ISO_PATH=$WORK_DIR/$ISO_FILE
DIGEST_PATH=$WORK_DIR/$ISO_FILE.DIGESTS

if [ ! -s "$ISO_PATH" ]; then
  log "Downloading $ISO_URL"
  curl -fsSL --retry 3 -C - "$ISO_URL" -o "$ISO_PATH"
else
  log "Reusing cached ISO $ISO_PATH"
fi

log "Fetching and verifying SHA512 digest"
curl -fsSL --retry 3 "$DIGEST_URL" -o "$DIGEST_PATH"
EXPECTED=$(awk -v name="$ISO_FILE" 'length($1) == 128 && $2 == name {print $1; exit}' "$DIGEST_PATH")
[ -n "$EXPECTED" ] || fail "Could not find SHA512 digest for $ISO_FILE in $DIGEST_PATH"
ACTUAL=$(sha512_file "$ISO_PATH")
if [ "$ACTUAL" != "$EXPECTED" ]; then
  rm -f "$ISO_PATH"
  fail "SHA512 mismatch for $ISO_FILE"
fi

mkdir -p "$(dirname "$OUTPUT")"
TMP_OUTPUT=$OUTPUT.tmp
rm -f "$TMP_OUTPUT"
log "Writing Gentoo bootable ISO image to $OUTPUT"
cp "$ISO_PATH" "$TMP_OUTPUT"
mv "$TMP_OUTPUT" "$OUTPUT"
log "Gentoo image written: $OUTPUT"
