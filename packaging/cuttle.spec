# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for Cuttle.

Produces a standalone dist/Cuttle/ directory containing:
- cuttle.exe: CLI converter (console=True)
- cuttlectl.exe: Ultra-fast Win32 native right-click dispatcher
- cuttle-worker.exe: Background worker daemon (console=False)
- cuttle_shell.dll: Native COM Explorer context menu DLL
- AppxManifest.xml: Sparse package identity manifest for Windows 11
"""

from pathlib import Path
import sys

block_cipher = None

ROOT_DIR = Path(SPECPATH).resolve().parent

from PyInstaller.utils.hooks import collect_data_files

# Data files: formats.toml, edges.toml, assets, AppxManifest, and library models/templates
datas = [
    (str(ROOT_DIR / "cuttle" / "registry" / "*.toml"), "cuttle/registry"),
    (str(ROOT_DIR / "assets" / "*.*"), "assets"),
    (str(ROOT_DIR / "packaging" / "AppxManifest.xml"), "packaging"),
    (str(ROOT_DIR / "scripts" / "register_sparse_package.ps1"), "scripts"),
    (str(ROOT_DIR / "scripts" / "unregister_sparse_package.ps1"), "scripts"),
]
datas += collect_data_files("pymupdf")
datas += collect_data_files("docx")
icon_path = str(ROOT_DIR / "assets" / "cuttle.ico")

# Binaries: vendor tools and native C++ binaries
binaries = []
vendor_dir = ROOT_DIR / "vendor"
if vendor_dir.is_dir():
    for exe in vendor_dir.glob("*.exe"):
        binaries.append((str(exe), "vendor"))

# Native Windows COM shell DLL if compiled
native_dll = ROOT_DIR / "cuttle" / "platform" / "windows" / "shell_extension" / "cuttle_shell.dll"
if native_dll.is_file():
    binaries.append((str(native_dll), "."))

# 1. cuttle CLI executable
a_cli = Analysis(
    [str(ROOT_DIR / "cuttle" / "cli.py")],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "typer",
        "pillow_heif",
        "filetype",
        "psutil",
        "pypdf",
        "pdf2docx",
        "pymupdf",
        "PIL",
    ],
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

# 2. cuttle-worker daemon executable
a_worker = Analysis(
    [str(ROOT_DIR / "cuttle" / "worker" / "main.py")],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PySide6",
        "windows_toasts",
        "pywin32",
        "win32file",
        "win32pipe",
        "win32job",
        "pdf2docx",
        "pymupdf",
        "pypdf",
        "PIL",
    ],
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

# 3. cuttlectl fallback Python launcher (overridden by native binary if compiled)
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

# COLLECT all executables and shared dependencies into dist/Cuttle/
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
