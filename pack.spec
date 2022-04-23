# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

analysis = Analysis(  # type:ignore # noqa:F821
    ["Solsol.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("./module", "./module"),
        ("./resource", "./resource"),
    ],
    hiddenimports=(
        []
        + collect_submodules("talib")
        + collect_submodules("numpy")
        + collect_submodules("pandas")
        + collect_submodules("scipy")
        + collect_submodules("PyQt6")
        + collect_submodules("pyqtgraph")
        + collect_submodules("requests")
        + collect_submodules("apscheduler")
        + collect_submodules("timesetter")
        + collect_submodules("websocket-client")
        + collect_submodules("pygments")
        + collect_submodules("dill")
        + collect_submodules("pyzipper")
        + collect_submodules("getmac")
        + collect_submodules("yapf")
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(  # type:ignore # noqa:F821
    analysis.pure,
    analysis.zipped_data,
    cipher=block_cipher,
)

exe = EXE(  # type:ignore # noqa:F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Solsol",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon="./resource/image_logo.ico",
)

coll = COLLECT(  # type:ignore # noqa:F821
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Solsol",
)
