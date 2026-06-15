# Agent Instructions

- Keep release notes as real Markdown with actual newlines.
- Do not pass escaped `\n` sequences to `gh release create --notes` or `gh release edit --notes`; GitHub renders them literally.
- For GitHub releases, write notes to a temporary `.md` file or use a heredoc, then pass `--notes-file <file>`.
- Do not commit generated release artifacts such as `build/`, `dist/`, `standalone-release/`, or `Alpine USB Installer.spec`.
- Before pushing, run at least:
  - `python3 -m py_compile alpine-usb gui.py cli.py tui.py`
  - `bash -n build-alpine-usb.sh configure-alpine-usb.sh scripts/build-macos-dmg.sh scripts/package-release-assets.sh`
