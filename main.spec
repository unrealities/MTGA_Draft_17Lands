# -*- mode: python ; coding: utf-8 -*-
import sys

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("themes/*.tcl", "themes"),
        # The card-prior assets must ship with the app: the loader resolves
        # them relative to the bundled advisor module, and a release build
        # without them silently loses the entire prior feature.
        ("assets/models/card_prior_z_table.npz", "assets/models"),
        ("assets/models/card_prior_z_table_manifest.json", "assets/models"),
        ("assets/models/card_prior.npz", "assets/models"),
        ("assets/models/card_prior_manifest.json", "assets/models"),
        ("assets/models/card_prior_nr.npz", "assets/models"),
        ("assets/models/card_prior_nr_manifest.json", "assets/models"),
    ],
    hiddenimports=[
        "jaraco.text",
        "platformdirs",
        "importlib_metadata",
        "zipp",
        "PIL._tkinter_finder",
        "PIL._imagingtk_finder",
    ],
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
