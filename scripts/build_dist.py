"""Comprehensive distribution builder for Cuttle (P6-01).

Per TRD task card P6-01:
- Compiles native C++ launcher and COM shell extension DLL.
- Builds PyInstaller package dist/Cuttle/.
- Builds Inno Setup installer (dist/Cuttle-Setup-x64.exe) if iscc is available.
- Packages portable distribution archive (dist/cuttle-portable-x64.zip).
- Calculates and writes SHA256SUMS.txt for all distribution artifacts.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
APP_DIST_DIR = DIST_DIR / "Cuttle"


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA256 digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_iscc() -> str | None:
    """Locate Inno Setup compiler (iscc) in PATH or standard installation paths."""
    found = shutil.which("iscc")
    if found:
        return found

    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Inno Setup 6"
        / "iscc.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Inno Setup 6" / "iscc.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)

    return None


def build_native_components() -> None:
    """Build native C++ launcher and COM shell extension DLL."""
    print("--> Step 1: Building native C++ launcher...")
    launcher_script = ROOT_DIR / "scripts" / "build_launcher.py"
    subprocess.run([sys.executable, str(launcher_script)], check=True)

    print("--> Step 2: Building native COM shell extension DLL...")
    shell_script = ROOT_DIR / "scripts" / "build_shell_extension.py"
    subprocess.run([sys.executable, str(shell_script)], check=True)


def build_pyinstaller() -> None:
    """Compile Python executables into dist/Cuttle/ via PyInstaller."""
    print("--> Step 3: Compiling Python executables with PyInstaller...")
    spec_file = ROOT_DIR / "packaging" / "cuttle.spec"
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_file)],
        check=True,
    )


def stage_distribution_folder() -> None:
    """Ensure all required runtime files, scripts, and native binaries exist in dist/Cuttle/."""
    APP_DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Native launcher (cuttlectl.exe)
    native_launcher = ROOT_DIR / "cuttle" / "platform" / "windows" / "launcher" / "cuttlectl.exe"
    if native_launcher.is_file():
        shutil.copy2(native_launcher, APP_DIST_DIR / "cuttlectl.exe")

    # 2. Native COM shell extension (cuttle_shell.dll)
    native_dll = (
        ROOT_DIR / "cuttle" / "platform" / "windows" / "shell_extension" / "cuttle_shell.dll"
    )
    if native_dll.is_file():
        shutil.copy2(native_dll, APP_DIST_DIR / "cuttle_shell.dll")

    # 3. Scripts and packaging manifest
    scripts_dest = APP_DIST_DIR / "scripts"
    scripts_dest.mkdir(exist_ok=True)
    shutil.copy2(
        ROOT_DIR / "scripts" / "register_sparse_package.ps1",
        scripts_dest / "register_sparse_package.ps1",
    )
    shutil.copy2(
        ROOT_DIR / "scripts" / "unregister_sparse_package.ps1",
        scripts_dest / "unregister_sparse_package.ps1",
    )

    pkg_dest = APP_DIST_DIR / "packaging"
    pkg_dest.mkdir(exist_ok=True)
    shutil.copy2(
        ROOT_DIR / "packaging" / "AppxManifest.xml",
        pkg_dest / "AppxManifest.xml",
    )

    # 4. Registry definitions
    reg_dest = APP_DIST_DIR / "cuttle" / "registry"
    reg_dest.mkdir(parents=True, exist_ok=True)
    for toml_file in (ROOT_DIR / "cuttle" / "registry").glob("*.toml"):
        shutil.copy2(toml_file, reg_dest / toml_file.name)

    # 5. Assets
    assets_dest = APP_DIST_DIR / "assets"
    assets_dest.mkdir(exist_ok=True)
    for asset in (ROOT_DIR / "assets").glob("*.*"):
        shutil.copy2(asset, assets_dest / asset.name)

    # 6. Vendored tools (ffmpeg, ffprobe, pandoc)
    vendor_src = ROOT_DIR / "vendor"
    if vendor_src.is_dir():
        vendor_dest = APP_DIST_DIR / "vendor"
        vendor_dest.mkdir(exist_ok=True)
        for exe_file in vendor_src.glob("*.exe"):
            shutil.copy2(exe_file, vendor_dest / exe_file.name)


def create_portable_zip() -> Path:
    """Package the standalone dist/Cuttle directory into a portable zip."""
    zip_path = DIST_DIR / "cuttle-portable-x64.zip"
    print(f"--> Creating portable archive: {zip_path.name}...")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for file in APP_DIST_DIR.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(DIST_DIR)
                z.write(file, arcname)

    return zip_path


def build_inno_setup_installer() -> Path | None:
    """Compile Inno Setup script if iscc is available."""
    iscc = find_iscc()
    if not iscc:
        print("--> Note: Inno Setup compiler (iscc) not found; skipping installer build.")
        return None

    iss_script = ROOT_DIR / "packaging" / "installer.iss"
    print(f"--> Building installer with Inno Setup: {iscc}...")
    subprocess.run([iscc, str(iss_script)], check=True)
    installer_path = DIST_DIR / "Cuttle-Setup-x64.exe"
    return installer_path if installer_path.is_file() else None


def generate_checksums() -> Path:
    """Write SHA256SUMS.txt for all built release archives and installers."""
    checksum_file = DIST_DIR / "SHA256SUMS.txt"
    entries: list[str] = []

    for item in sorted(DIST_DIR.glob("*")):
        if item.is_file() and item.name != "SHA256SUMS.txt" and item.suffix in (".exe", ".zip"):
            digest = compute_sha256(item)
            entries.append(f"{digest}  {item.name}")
            print(f"    SHA256 ({item.name}): {digest}")

    checksum_file.write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"--> Wrote checksums to: {checksum_file.name}")
    return checksum_file


def main() -> None:
    """Orchestrate the complete distribution build."""
    print("========================================")
    print("   Cuttle Distribution Packager (P6-01) ")
    print("========================================")

    build_native_components()
    build_pyinstaller()
    stage_distribution_folder()
    create_portable_zip()
    build_inno_setup_installer()
    generate_checksums()

    print("\n[SUCCESS] Distribution packaging completed successfully.")


if __name__ == "__main__":
    main()
