#!/usr/bin/env bash
# Build release assets. Terminal binary is shipped in a tarball so +x survives download.
set -euo pipefail

cd "$(dirname "$0")/.."

version="${1:-}"
if [ -z "$version" ]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 0.2.0" >&2
  exit 2
fi
version="${version#v}"

assets_dir="dist/release-assets"
terminal_pkg_dir="dist/terminal-binary"
terminal_base="ledit-${version}-macos-arm64-terminal"
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
  --name "ledit" \
  --collect-submodules "ledit_core" \
  --add-data "ledit_core/backend/scripts/build-alpine-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-alpine-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-arch-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-arch-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-debian-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-debian-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-fedora-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-gentoo-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-gentoo-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-opensuse-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-opensuse-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-rhel-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-rhel-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-slackware-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-slackware-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-ubuntu-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-ubuntu-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/build-void-usb.sh:ledit_core/backend/scripts" \
  --add-data "ledit_core/backend/scripts/configure-void-usb.sh:ledit_core/backend/scripts" \
  --add-data "README.md:." \
  --add-data "LICENSE:." \
  --add-data "ledit_core/backend/efi-fallback:ledit_core/backend/efi-fallback" \
  --add-data "ledit_core/backend/docker/Dockerfile.builder:ledit_core/backend/docker" \
  --add-data "ledit_core/backend/docker/Dockerfile.gentoo-builder:ledit_core/backend/docker" \
  ledit

rm -rf "$assets_dir" "$terminal_pkg_dir"
mkdir -p "$assets_dir" "$terminal_pkg_dir"

cp "dist/LEDIT.dmg" "$assets_dir/ledit-${version}-macos-arm64-gui.dmg"
cp dist/ledit "$terminal_pkg_dir/ledit"
chmod 755 "$terminal_pkg_dir/ledit"

# Raw GitHub downloads do not preserve Unix executable bits. A tarball does.
"${tar_cmd[@]}" -C "$terminal_pkg_dir" -czf "$assets_dir/${terminal_base}.tar.gz" ledit

python3 - "$version" <<'PY'
import sys, tarfile, zipfile
from pathlib import Path

version = sys.argv[1]
root = Path.cwd()
out = root / "dist" / "release-assets"
base = f"ledit-{version}-terminal-source"
files = [
    "ledit",
    "ledit_core",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "pyproject.toml",
    "ledit_core/tests",
    "docs",
    ".dockerignore",
    "ledit_core/backend/docker/Dockerfile.builder",
    "ledit_core/backend/docker/Dockerfile.gentoo-builder",
    "scripts/check-project.sh",
    "scripts/check-image-compile.sh",
    "scripts/validate-config-matrix.sh",
]
files.extend(str(path) for path in sorted(root.glob("ledit_core/backend/scripts/build-*-usb.sh")))
files.extend(str(path) for path in sorted(root.glob("ledit_core/backend/scripts/configure-*-usb.sh")))


def wanted(path: Path) -> bool:
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


def arcname_for(path: Path, name: str) -> str:
    rel = path.relative_to(root) if path.is_absolute() else Path(name)
    return f"{base}/{rel}"

with tarfile.open(out / f"{base}.tar.gz", "w:gz") as tar:
    for name in files:
        path = Path(name)
        if not path.is_absolute():
            path = root / path
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and wanted(child):
                    tar.add(child, arcname=f"{base}/{path.relative_to(root)}/{child.relative_to(path)}")
        elif path.exists():
            tar.add(path, arcname=arcname_for(path, name))
    efi = root / "ledit_core" / "backend" / "efi-fallback"
    if efi.exists():
        tar.add(efi, arcname=f"{base}/ledit_core/backend/efi-fallback")

with zipfile.ZipFile(out / f"{base}.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for name in files:
        path = Path(name)
        if not path.is_absolute():
            path = root / path
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and wanted(child):
                    zf.write(child, f"{base}/{path.relative_to(root)}/{child.relative_to(path)}")
        elif path.exists():
            zf.write(path, arcname_for(path, name))
    efi = root / "ledit_core" / "backend" / "efi-fallback"
    if efi.exists():
        for path in efi.rglob("*"):
            if path.is_file():
                zf.write(path, f"{base}/ledit_core/backend/efi-fallback/{path.relative_to(efi)}")
PY

(
  cd "$assets_dir"
  shasum -a 256 ledit-"${version}"-* > SHA256SUMS.txt
)

ls -lh "$assets_dir"
