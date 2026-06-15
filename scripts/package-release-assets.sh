#!/usr/bin/env bash
# Build release assets. Terminal binary is shipped in a tarball so +x survives download.
set -euo pipefail

cd "$(dirname "$0")/.."

version="${1:-}"
if [ -z "$version" ]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 0.1.7" >&2
  exit 2
fi
version="${version#v}"

assets_dir="dist/release-assets"
terminal_pkg_dir="dist/terminal-binary"
source_base="alpine-usb-installer-${version}-terminal-source"
terminal_base="alpine-usb-installer-${version}-macos-arm64-terminal"
if [ -n "${PYINSTALLER:-}" ]; then
  PYINSTALLER_CMD="$PYINSTALLER"
elif [ -x ".qtvenv/bin/pyinstaller" ]; then
  PYINSTALLER_CMD=".qtvenv/bin/pyinstaller"
else
  PYINSTALLER_CMD="pyinstaller"
fi

tar_cmd=(tar --format=ustar --owner=0 --group=0 --numeric-owner)
if ! tar --version >/dev/null 2>&1; then
  # BSD tar on macOS does not support GNU owner flags in the same way.
  tar_cmd=(tar)
fi

scripts/build-macos-dmg.sh

"$PYINSTALLER_CMD" \
  --noconfirm \
  --onefile \
  --console \
  --name "alpine-usb" \
  --hidden-import "cli" \
  --hidden-import "tui" \
  --add-data "build-alpine-usb.sh:." \
  --add-data "configure-alpine-usb.sh:." \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "efi-fallback:efi-fallback" \
  alpine-usb

rm -rf "$assets_dir" "$terminal_pkg_dir"
mkdir -p "$assets_dir" "$terminal_pkg_dir"

cp "dist/Alpine USB Installer.dmg" "$assets_dir/alpine-usb-installer-${version}-macos-arm64-gui.dmg"
cp dist/alpine-usb "$terminal_pkg_dir/alpine-usb"
chmod 755 "$terminal_pkg_dir/alpine-usb"

# Raw GitHub downloads do not preserve Unix executable bits. A tarball does.
"${tar_cmd[@]}" -C "$terminal_pkg_dir" -czf "$assets_dir/${terminal_base}.tar.gz" alpine-usb

python3 - "$version" <<'PY'
import sys, tarfile, zipfile
from pathlib import Path

version = sys.argv[1]
root = Path.cwd()
out = root / "dist" / "release-assets"
base = f"alpine-usb-installer-{version}-terminal-source"
files = [
    "alpine-usb",
    "cli.py",
    "tui.py",
    "build-alpine-usb.sh",
    "configure-alpine-usb.sh",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "repositories",
]

with tarfile.open(out / f"{base}.tar.gz", "w:gz") as tar:
    for name in files:
        path = root / name
        if path.exists():
            tar.add(path, arcname=f"{base}/{name}")
    efi = root / "efi-fallback"
    if efi.exists():
        tar.add(efi, arcname=f"{base}/efi-fallback")

with zipfile.ZipFile(out / f"{base}.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for name in files:
        path = root / name
        if path.exists():
            zf.write(path, f"{base}/{name}")
    efi = root / "efi-fallback"
    if efi.exists():
        for path in efi.rglob("*"):
            if path.is_file():
                zf.write(path, f"{base}/efi-fallback/{path.relative_to(efi)}")
PY

(
  cd "$assets_dir"
  shasum -a 256 alpine-usb-installer-${version}-* > SHA256SUMS.txt
)

ls -lh "$assets_dir"
