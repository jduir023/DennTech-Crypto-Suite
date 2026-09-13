# -*- mode: python ; coding: utf-8 -*-
import os

project_root = os.path.abspath(SPECPATH)

a = Analysis(
    [os.path.join(project_root, 'main.py')],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'data'), 'data'),
        (os.path.join(project_root, 'suite_logo.png'), '.'),
        (os.path.join(project_root, 'suite_icon.ico'), '.'),
        (os.path.join(project_root, 'crypto-suite-manual.html'), '.'),
    ],
    hiddenimports=[
        'license_manager',
        'splash_screen',
        'engines',
        'engines.bot_bridge',
        'engines.data_fetcher',
        'engines.dca_engine',
        'engines.history_engine',
        'engines.portfolio_engine',
        'engines.risk_engine',
        'engines.strategy_engine',
        'engines.tax_engine',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.QtCore',
        'matplotlib',
        'matplotlib.backends.backend_qtagg',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide2', 'PySide6', 'tkinter', 'customtkinter'],
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
    name='DennTechCryptoSuite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'suite_icon.ico'),
)
