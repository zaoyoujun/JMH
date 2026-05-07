from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()
APP_ICON = PROJECT_ROOT / "assets" / "app.ico"

hiddenimports = []
for package_name in ("webview", "uvicorn", "fastapi", "starlette", "clickhouse_connect"):
    hiddenimports += collect_submodules(package_name)

datas = [
    (str(PROJECT_ROOT / "MoviePop-front"), "frontend"),
]
for package_name in ("webview", "clickhouse_connect"):
    datas += collect_data_files(package_name)


a = Analysis(
    [str(PROJECT_ROOT / "MoviePop-backend" / "run_backend.py")],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "MoviePop-backend")],
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
    [],
    exclude_binaries=True,
    name="MoviePop",
    icon=str(APP_ICON),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MoviePop",
)
