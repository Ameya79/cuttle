"""Build script to compile the native C++ cuttle_shell.dll COM extension.

Per task cards P4-02 and P4-03:
- Compiles the IExplorerCommand in-process COM server.
- Produces cuttle/platform/windows/shell_extension/cuttle_shell.dll.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIR_PATH = ROOT_DIR / "cuttle" / "platform" / "windows" / "shell_extension"
OUT_DLL = DIR_PATH / "cuttle_shell.dll"
DEF_FILE = DIR_PATH / "cuttle_shell.def"
SRC_FILES = [
    DIR_PATH / "cuttle_command.cpp",
    DIR_PATH / "dllmain.cpp",
]


def build_with_gcc(gxx_path: str) -> bool:
    """Compile shared library with g++."""
    cmd = [
        gxx_path,
        "-std=c++17",
        "-O3",
        "-shared",
        "-static",
        "-s",
        str(DEF_FILE),
        *[str(f) for f in SRC_FILES],
        "-o",
        str(OUT_DLL),
        "-lole32",
        "-luuid",
        "-lshlwapi",
        "-lshell32",
        "-ladvapi32",
    ]
    print(f"Compiling shell extension with: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Compilation error:\n{res.stderr}", file=sys.stderr)
        return False
    print(f"Successfully compiled COM shell DLL to {OUT_DLL} ({OUT_DLL.stat().st_size} bytes)")
    return True


def main() -> int:
    if sys.platform != "win32":
        print("Windows COM shell extension compilation only supported on Windows.", file=sys.stderr)
        return 0

    DIR_PATH.mkdir(parents=True, exist_ok=True)
    for src in SRC_FILES:
        if not src.is_file():
            print(f"Source file not found: {src}", file=sys.stderr)
            return 1

    gxx = shutil.which("g++")
    if gxx and build_with_gcc(gxx):
        return 0

    print("Error: No suitable C++ compiler (g++) found on PATH.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
