# -*- mode: python ; coding: utf-8 -*-
"""Build portable : dist/Finish/Finish.exe. Lancé par scripts/build.ps1."""

from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "src" / "main.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "finish.png"), "."), (str(root / "arrivee.png"), ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Finish",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(root / "build" / "finish.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Finish",
)
