"""LibreOffice detection on Windows.

Per task card P3-02:
- Locates soffice.exe via App Paths registry keys and common Program Files directories.
- Probes version string using soffice --version.
- Zero COM / Word dependencies (LibreOffice only).
- Supports mockable path and registry lookups for test isolation.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OfficeInfo:
    """Information about detected LibreOffice installation."""

    installed: bool
    path: Path | None = None
    version: str | None = None
    name: str = "LibreOffice"


def _query_registry_app_path(sub_key: str) -> Path | None:
    """Query a Windows registry App Paths key for soffice.exe."""
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


def get_common_office_paths() -> list[Path]:
    """Return list of standard installation paths for LibreOffice on Windows."""
    candidates: list[Path] = []

    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidates.append(Path(program_files) / "LibreOffice" / "program" / "soffice.exe")

    program_files_x86 = os.environ.get("PROGRAMFILES(X86)")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "LibreOffice" / "program" / "soffice.exe")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Programs" / "LibreOffice" / "program" / "soffice.exe"
        )

    return candidates


def probe_soffice_version(soffice_path: Path) -> str | None:
    """Run soffice --version and extract version string."""
    try:
        res = subprocess.run(
            [str(soffice_path), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout:
            return res.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return None


def detect_office(
    search_paths: list[Path] | None = None,
    check_registry: bool = True,
    probe_version: bool = True,
) -> OfficeInfo:
    """Find LibreOffice on the host system.

    Parameters:
        search_paths: Optional list of candidate directories or exe paths.
        check_registry: Whether to query Windows App Paths registry keys.
        probe_version: Whether to invoke the binary to fetch its version string.

    Returns:
        OfficeInfo instance with installation status and version.
    """
    # 1. Custom search paths if provided
    if search_paths:
        for p in search_paths:
            candidate = p / "soffice.exe" if p.is_dir() else p
            if candidate.is_file():
                version = probe_soffice_version(candidate) if probe_version else "detected"
                return OfficeInfo(installed=True, path=candidate, version=version)

    # 2. Query Windows Registry App Paths
    if check_registry and sys.platform == "win32":
        app_path = _query_registry_app_path(
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\soffice.exe"
        )
        if app_path and app_path.is_file():
            version = probe_soffice_version(app_path) if probe_version else "detected"
            return OfficeInfo(installed=True, path=app_path, version=version)

    # 3. Check system PATH
    which_soffice = shutil.which("soffice")
    if which_soffice:
        cand = Path(which_soffice)
        if cand.is_file():
            version = probe_soffice_version(cand) if probe_version else "detected"
            return OfficeInfo(installed=True, path=cand, version=version)

    # 4. Standard installation directories
    for cand in get_common_office_paths():
        if cand.is_file():
            version = probe_soffice_version(cand) if probe_version else "detected"
            return OfficeInfo(installed=True, path=cand, version=version)

    return OfficeInfo(installed=False, path=None, version=None)
