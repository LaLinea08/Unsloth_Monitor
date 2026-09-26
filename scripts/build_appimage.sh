#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This build targets Linux x86_64 only.' >&2
  exit 1
fi
python -m PyInstaller --noconfirm --clean packaging/unsloth-monitor.spec
# A fresh directory prevents removed libraries surviving incremental builds.
appdir="$(mktemp -d "$PWD/build/AppDir.XXXXXXXX")"
mkdir -p "$appdir/usr/bin"
cp -a dist/unsloth-monitor/. "$appdir/usr/bin/"
cp packaging/AppRun "$appdir/AppRun"
chmod +x "$appdir/AppRun"
cp packaging/unsloth-monitor.desktop "$appdir/"
cp src/unsloth_monitor/assets/unsloth-monitor.svg "$appdir/"
cp src/unsloth_monitor/assets/unsloth-monitor.svg "$appdir/.DirIcon"
# Executable tooling must be fetched and checksum-verified explicitly by CI.
: "${APPIMAGETOOL:?Set APPIMAGETOOL to the verified extracted appimagetool AppRun}"
: "${APPIMAGE_RUNTIME:?Set APPIMAGE_RUNTIME to the checksum-verified x86_64 runtime}"
ARCH=x86_64 "$APPIMAGETOOL" --runtime-file "$APPIMAGE_RUNTIME" "$appdir" dist/Unsloth-Monitor-x86_64.AppImage
sha256sum dist/Unsloth-Monitor-x86_64.AppImage > dist/SHA256SUMS
