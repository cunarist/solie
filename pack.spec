# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils import hooks

# ■■■■■ files to include ■■■■■

datas = [
    ("./module", "./module"),
    ("./resource", "./resource"),
]
binaries = []
hiddenimports = []

# ■■■■■ packages to complete ■■■■■

packages_to_complete = [
    "talib",
    "pygments",
    "yapf",
    "timesetter",
]
for package in packages_to_complete:
    new_lists = hooks.collect_all(package)
    datas += new_lists[0]
    binaries += new_lists[1]
    hiddenimports += new_lists[2]

# ■■■■■ analysis ■■■■■

analysis = Analysis(  # type:ignore # noqa:F821
    ["Solsol.py"],
    pathex=[],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ■■■■■ outputs ■■■■■

pyz = PYZ(  # type:ignore # noqa:F821
    analysis.pure,
    analysis.zipped_data,
    cipher=None,
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
