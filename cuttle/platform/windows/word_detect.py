"""Microsoft Word detection on Windows.

Detects whether Microsoft Word is installed via Windows App Paths registry
keys, standard Program Files directories, or COM registration.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WordInfo:
    """Information about detected Microsoft Word installation."""

    installed: bool
    path: Path | None = None
    version: str | None = None
    name: str = "Microsoft Word"


def _query_registry_app_path(sub_key: str) -> Path | None:
    """Query a Windows registry App Paths key for WINWORD.EXE."""
    if sys.platform != "win32":
        return None

    import winreg

    for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val:
                    candidate = Path(str(val).strip('"'))
                    if candidate.is_file():
                        return candidate
        except (OSError, FileNotFoundError):
            continue
    return None


def get_common_word_paths() -> list[Path]:
    """Return standard installation paths for Microsoft Word on Windows."""
    candidates: list[Path] = []

    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(
            Path(program_files) / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE"
        )
        candidates.append(Path(program_files) / "Microsoft Office" / "Office16" / "WINWORD.EXE")
        candidates.append(Path(program_files) / "Microsoft Office" / "Office15" / "WINWORD.EXE")

    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    if program_files_x86:
        candidates.append(
            Path(program_files_x86) / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE"
        )
        candidates.append(Path(program_files_x86) / "Microsoft Office" / "Office16" / "WINWORD.EXE")
        candidates.append(Path(program_files_x86) / "Microsoft Office" / "Office15" / "WINWORD.EXE")

    return candidates


def detect_word(
    search_paths: list[Path] | None = None,
    check_registry: bool = True,
) -> WordInfo:
    """Find Microsoft Word on the host system.

    Parameters:
        search_paths: Optional list of candidate directories or exe paths.
        check_registry: Whether to query Windows App Paths registry keys.

    Returns:
        WordInfo instance with installation status and path.
    """
    if sys.platform != "win32":
        return WordInfo(installed=False, path=None, version=None)

    # 1. Custom search paths if provided
    if search_paths:
        for p in search_paths:
            candidate = p / "WINWORD.EXE" if p.is_dir() else p
            if candidate.is_file():
                return WordInfo(installed=True, path=candidate, version="Office Word")

    # 2. Query Windows Registry App Paths
    if check_registry:
        app_path = _query_registry_app_path(
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe"
        )
        if app_path and app_path.is_file():
            return WordInfo(installed=True, path=app_path, version="Office Word")

    # 3. Check system PATH
    which_word = shutil.which("winword") or shutil.which("WINWORD.EXE")
    if which_word:
        cand = Path(which_word)
        if cand.is_file():
            return WordInfo(installed=True, path=cand, version="Office Word")

    # 4. Standard installation directories
    for cand in get_common_word_paths():
        if cand.is_file():
            return WordInfo(installed=True, path=cand, version="Office Word")

    # 5. Check COM registration as fallback
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"Word.Application\CurVer", 0, winreg.KEY_READ
        ) as key:
            val, _ = winreg.QueryValueEx(key, "")
            if val:
                return WordInfo(installed=True, path=None, version=str(val))
    except (OSError, FileNotFoundError):
        pass

    return WordInfo(installed=False, path=None, version=None)
