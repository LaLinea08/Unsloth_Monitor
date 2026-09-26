# Build on Linux x86_64; stdlib curses uses the user's terminal appearance.
from pathlib import Path

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
    excludes=['PySide6', 'shiboken6', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='unsloth-monitor',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='unsloth-monitor')
