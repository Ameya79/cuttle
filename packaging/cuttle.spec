# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for Cuttle.

Produces a standalone dist/Cuttle/ directory containing:
- cuttle.exe: CLI converter (console=True)
- cuttlectl.exe: Ultra-fast right-click dispatcher (console=False)
- cuttle-worker.exe: Background worker daemon (console=False)
"""

from pathlib import Path
import sys

block_cipher = None

ROOT_DIR = Path(SPECPATH).resolve().parent

# Data files: formats.toml, edges.toml, and assets
datas = [
    (str(ROOT_DIR / "cuttle" / "registry" / "*.toml"), "cuttle/registry"),
    (str(ROOT_DIR / "assets" / "*.*"), "assets"),
]
icon_path = str(ROOT_DIR / "assets" / "cuttle.ico")

# Binaries: vendor tools if present
binaries = []
vendor_dir = ROOT_DIR / "vendor"
if vendor_dir.is_dir():
    for exe in vendor_dir.glob("*.exe"):
        binaries.append((str(exe), "vendor"))

# 1. cuttle CLI executable
a_cli = Analysis(
    [str(ROOT_DIR / "cuttle" / "cli.py")],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["typer", "pillow_heif", "filetype", "psutil"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="cuttle",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# 2. cuttlectl fast launcher executable
a_ctl = Analysis(
    [str(ROOT_DIR / "cuttle" / "worker" / "cuttlectl.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=["pywin32", "win32file", "win32pipe"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_ctl = PYZ(a_ctl.pure, a_ctl.zipped_data, cipher=block_cipher)
exe_ctl = EXE(
    pyz_ctl,
    a_ctl.scripts,
    [],
    exclude_binaries=True,
    name="cuttlectl",
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
    icon=icon_path,
)

# 3. cuttle-worker daemon executable
a_worker = Analysis(
    [str(ROOT_DIR / "cuttle" / "worker" / "main.py")],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=["PySide6", "windows_toasts", "pywin32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz_worker = PYZ(a_worker.pure, a_worker.zipped_data, cipher=block_cipher)
exe_worker = EXE(
    pyz_worker,
    a_worker.scripts,
    [],
    exclude_binaries=True,
    name="cuttle-worker",
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
    icon=icon_path,
)

# COLLECT all three executables and shared dependencies into dist/Cuttle/
coll = COLLECT(
    exe_cli,
    a_cli.binaries,
    a_cli.zipfiles,
    a_cli.datas,
    exe_ctl,
    a_ctl.binaries,
    a_ctl.zipfiles,
    a_ctl.datas,
    exe_worker,
    a_worker.binaries,
    a_worker.zipfiles,
    a_worker.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Cuttle",
)
