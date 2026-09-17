# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('client', 'client'),
    ('scripts/ViGEmBusSetup_x64.msi', '.'),
    ('scripts/ViGEmBusSetup_x64.msi', 'scripts'),
    ('scripts/benchmark_suite.py', 'scripts'),
    ('scripts/benchmark_suite.py', '.'),
    ('scripts/viva_defense_suite.py', 'scripts'),
    ('scripts/viva_defense_suite.py', '.'),
    ('gui/logo.png', 'gui'),
    ('gui/logo.png', '.'),
    ('gui/logo.ico', 'gui'),
    ('gui/logo.ico', '.')
]
binaries = []
hiddenimports = []
tmp_ret = collect_all('vgamepad')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('qrcode')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('websockets')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['terminal_main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['customtkinter', 'tkinter', 'PIL', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Controller-Terminal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui/logo.ico',
)
