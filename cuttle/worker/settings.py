"""User settings and autostart management for Cuttle.

Configuration is stored in %APPDATA%\\Cuttle\\settings.toml.
Autostart is controlled via HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def default_max_jobs() -> int:
    """Default concurrency limit: half of logical CPU cores (minimum 1)."""
    cores = os.cpu_count() or 2
    return max(1, cores // 2)


@dataclass
class CuttleSettings:
    """User preferences stored in settings.toml."""

    output_dir: Path | None = None
    max_parallel_jobs: int = default_max_jobs()
    autostart: bool = True
    notifications_enabled: bool = True
    collision_suffix: str = "(converted)"


def get_default_settings_path() -> Path:
    """Return default settings file path in Roaming AppData."""
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    return base / "Cuttle" / "settings.toml"


def get_default_worker_cmd() -> str:
    """Resolve default command string to execute cuttle-worker daemon."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        worker_exe = exe_dir / "cuttle-worker.exe"
        if worker_exe.exists():
            return f'"{worker_exe}"'

    worker_on_path = shutil.which("cuttle-worker")
    if worker_on_path:
        return f'"{worker_on_path}"'

    return f'"{sys.executable}" -m cuttle.worker.main'


def serialize_settings(settings: CuttleSettings) -> str:
    """Serialize CuttleSettings to standard TOML string format."""
    out_dir_str = settings.output_dir.as_posix() if settings.output_dir else ""
    lines = [
        "# Cuttle Configuration File",
        "# Edit this file to configure default behavior.",
        "",
        f'output_dir = "{out_dir_str}"',
        f"max_parallel_jobs = {settings.max_parallel_jobs}",
        f"autostart = {'true' if settings.autostart else 'false'}",
        f"notifications_enabled = {'true' if settings.notifications_enabled else 'false'}",
        f'collision_suffix = "{settings.collision_suffix}"',
        "",
    ]
    return "\n".join(lines)


def load_settings(path: Path | None = None) -> CuttleSettings:
    """Load settings from TOML file, falling back to defaults on error."""
    p = Path(path or get_default_settings_path())
    if not p.is_file():
        return CuttleSettings()

    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
        raw_out = data.get("output_dir", "")
        out_dir = Path(raw_out) if raw_out else None
        return CuttleSettings(
            output_dir=out_dir,
            max_parallel_jobs=int(data.get("max_parallel_jobs", default_max_jobs())),
            autostart=bool(data.get("autostart", True)),
            notifications_enabled=bool(data.get("notifications_enabled", True)),
            collision_suffix=str(data.get("collision_suffix", "(converted)")),
        )
    except Exception as exc:
        logger.warning("Failed to load settings from %s, using defaults: %s", p, exc)
        return CuttleSettings()


def save_settings(settings: CuttleSettings, path: Path | None = None) -> Path:
    """Save settings to TOML file."""
    p = Path(path or get_default_settings_path())
    p.parent.mkdir(parents=True, exist_ok=True)
    content = serialize_settings(settings)
    p.write_text(content, encoding="utf-8")
    return p


def set_autostart_enabled(
    enabled: bool,
    run_key_base: str = r"Software\Microsoft\Windows\CurrentVersion\Run",
    root_key: Any = None,
    app_cmd: str | None = None,
) -> bool:
    """Enable or disable Cuttle autostart in the Windows Run registry key."""
    if sys.platform != "win32":
        return False

    import winreg

    root = root_key if root_key is not None else winreg.HKEY_CURRENT_USER
    try:
        k = winreg.CreateKey(root, run_key_base)
        try:
            if enabled:
                cmd = app_cmd or get_default_worker_cmd()
                winreg.SetValueEx(k, "Cuttle", 0, winreg.REG_SZ, cmd)
            else:
                with contextlib.suppress(FileNotFoundError):
                    winreg.DeleteValue(k, "Cuttle")
            return True
        finally:
            winreg.CloseKey(k)
    except OSError as exc:
        logger.warning("Failed to modify autostart registry: %s", exc)
        return False


def is_autostart_enabled(
    run_key_base: str = r"Software\Microsoft\Windows\CurrentVersion\Run",
    root_key: Any = None,
) -> bool:
    """Check whether Cuttle autostart is currently registered in Windows Run."""
    if sys.platform != "win32":
        return False

    import winreg

    root = root_key if root_key is not None else winreg.HKEY_CURRENT_USER
    try:
        k = winreg.OpenKey(root, run_key_base, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(k, "Cuttle")
            return True
        finally:
            winreg.CloseKey(k)
    except (FileNotFoundError, OSError):
        return False
