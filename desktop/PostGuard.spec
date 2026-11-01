# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


mediapipe_data, mediapipe_binaries, mediapipe_hiddenimports = collect_all(
    "mediapipe"
)

datas = mediapipe_data + [
    ("app/assets", "app/assets"),
    ("app/vision/models", "app/vision/models"),
    (
        "app/vision/session_monitoring/measurement_change_thresholds.json",
        "app/vision/session_monitoring",
    ),
]

a = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=mediapipe_binaries,
    datas=datas,
    hiddenimports=mediapipe_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["backend", "tests", "tools"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PostGuard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PostGuard",
)
