# -*- mode: python ; coding: utf-8 -*-
import sys

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("themes/*.tcl", "themes")],
    hiddenimports=["jaraco.text", "platformdirs", "importlib_metadata", "zipp"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="MTGA_Draft_Tool",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name="MTGA_Draft_Tool",
    )
    app = BUNDLE(
        coll,
        name="MTGA_Draft_Tool.app",
        icon=None,  # Add a path to an .icns file here if you have one
        bundle_identifier="com.unrealities.mtgadrafttool",
        info_plist={
            "NSHighResolutionCapable": "True",
            "LSBackgroundOnly": "False",
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="MTGA_Draft_Tool",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
