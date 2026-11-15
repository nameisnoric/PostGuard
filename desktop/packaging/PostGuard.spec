from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


desktop_root = Path(SPECPATH).resolve().parent
project_root = desktop_root.parent
backend_root = project_root / "backend"

mediapipe_data, mediapipe_binaries, mediapipe_hidden = collect_all(
    "mediapipe"
)

camera_card_hidden = collect_submodules(
    "camera_card",
    filter=lambda name: ".tests" not in name,
)

analysis = Analysis(
    [str(desktop_root / "app" / "main.py")],
    pathex=[
        str(desktop_root),
        str(backend_root),
    ],
    binaries=mediapipe_binaries,
    datas=[
        (
            str(desktop_root / "app" / "assets"),
            "app/assets",
        ),
        (
            str(desktop_root / "app" / "vision" / "models"),
            "app/vision/models",
        ),
        *mediapipe_data,
    ],
    hiddenimports=[
        *mediapipe_hidden,
        *camera_card_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
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

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PostGuard",
)
