# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)
app_dir = project_root / "app"

datas = [
    (str(app_dir / "resources"), "app/resources"),
    (str(project_root / "HELP.md"), "."),
    (str(project_root / "HELP.en.md"), "."),
    (str(project_root / "README.md"), "."),
]

hiddenimports = [
    "yaml",
]


a = Analysis(
    ["app/main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="FL-Atlas-Launcher",
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
    icon=str(app_dir / "resources" / "icons" / "fl_atlas_launcher_icon_512.png"),
)
