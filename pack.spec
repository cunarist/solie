# -*- coding: utf-8 -*-

from PyInstaller.utils import hooks

# ■■■■■ lists of files and folders to include ■■■■■

datas = []
binaries = []
hiddenimports = []

# ■■■■■ include needed files ■■■■■

datas.append(("./static", "./static"))

# ■■■■■ packages to complete ■■■■■

packages_to_complete = [
    "talib",
    "pyqtgraph",
    "timesetter",
    "pygments",
    "yapf",
    "tendo",
    "cryptography",
]
for package in packages_to_complete:
    new_lists = hooks.collect_all(package)
    datas += new_lists[0]
    binaries += new_lists[1]
    hiddenimports += new_lists[2]

# ■■■■■ analysis ■■■■■

a = Analysis(  # type:ignore # noqa:F821,VNE001
    ["Solie.py"],
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
    a.pure,
    a.zipped_data,
    cipher=None,
)

exe = EXE(  # type:ignore # noqa:F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Solie",
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
    icon="./static/product_icon.ico",
)

coll = COLLECT(  # type:ignore # noqa:F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Solie",
)
