# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WavePack Maker."""

from pathlib import Path

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

project_root = Path(SPECPATH).resolve()
icon_path = project_root / "assets" / "logo.ico"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(str(icon_path), 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WavePackMaker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.is_file() else None,
)
