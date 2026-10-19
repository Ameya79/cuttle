"""Build script to compile the native C++ cuttlectl launcher.

Per task card P4-01:
- Compiles cuttle/platform/windows/launcher/main.cpp into a standalone, windowless executable.
- Uses g++ (MinGW/UCRT64) or MSVC cl.exe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_FILE = ROOT_DIR / "cuttle" / "platform" / "windows" / "launcher" / "main.cpp"
OUT_FILE = ROOT_DIR / "cuttle" / "platform" / "windows" / "launcher" / "cuttlectl.exe"


def build_with_gcc(gxx_path: str) -> bool:
    """Compile with g++ using Win32 GUI subsystem (windowless)."""
    cmd = [
        gxx_path,
        "-std=c++17",
        "-O3",
        "-municode",
        "-mwindows",
        "-static",
        "-s",
        str(SRC_FILE),
        "-o",
        str(OUT_FILE),
        "-lshlwapi",
        "-lshell32",
    ]
    print(f"Compiling launcher with: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Compilation error:\n{res.stderr}", file=sys.stderr)
        return False
    print(f"Successfully compiled native launcher to {OUT_FILE} ({OUT_FILE.stat().st_size} bytes)")
    return True


def build_with_msvc(cl_path: str) -> bool:
    """Compile with MSVC cl.exe."""
    cmd = [
        cl_path,
        "/nologo",
        "/O2",
        "/std:c++17",
        "/EHsc",
        str(SRC_FILE),
        "/link",
        "/SUBSYSTEM:WINDOWS",
        f"/OUT:{OUT_FILE}",
        "shlwapi.lib",
        "shell32.lib",
        "user32.lib",
        "advapi32.lib",
    ]
    print(f"Compiling launcher with MSVC: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"MSVC compilation error:\n{res.stderr}\n{res.stdout}", file=sys.stderr)
        return False
    print(f"Successfully compiled native launcher to {OUT_FILE}")
    return True


def main() -> int:
    if sys.platform != "win32":
        print("Native Windows launcher compilation only supported on Windows.", file=sys.stderr)
        return 0

    if not SRC_FILE.is_file():
        print(f"Source file not found: {SRC_FILE}", file=sys.stderr)
        return 1

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    gxx = shutil.which("g++")
    if gxx and build_with_gcc(gxx):
        return 0

    cl = shutil.which("cl")
    if cl and build_with_msvc(cl):
        return 0

    print("Error: No suitable C++ compiler (g++ or cl.exe) found on PATH.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
