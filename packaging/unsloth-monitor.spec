# Build on Linux x86_64; stdlib curses uses the user's terminal appearance.
from pathlib import Path
import json

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'packaging' / 'entrypoint.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[(str(root / 'src' / 'unsloth_monitor' / 'assets'), 'unsloth_monitor/assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'shiboken6', 'tkinter', 'readline'],
    noarchive=False,
)
# Keep the actual origin of every collected native library for notice collection.
(root / 'build').mkdir(exist_ok=True)
(root / 'build' / 'bundled-binaries.json').write_text(
    json.dumps(list(a.binaries), indent=2), encoding='utf-8')
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='unsloth-monitor',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='unsloth-monitor')
