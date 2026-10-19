"""File Explorer Right-Click Registry Installer for Cuttle.

Registers dynamic cascading context menus under HKCU\\Software\\Classes:
- SystemFileAssociations\\.<ext>\\shell\\Cuttle -> ExtendedSubCommandsKey = Cuttle.menu.<fmt>
- Cuttle.menu.<fmt>\\shell\\<target>\\command -> "cuttlectl" "%1" <target>

Requires zero administrator privileges and maintains an audit manifest
(installed_keys.json) for clean, 100% leave-no-trace uninstallation.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Configuration for registry context menu installation."""

    root_key: Any = 0
    base_path: str = r"Software\Classes"
    cuttlectl_cmd: str | None = None
    icon_path: str | Path | None = None
    manifest_path: str | Path | None = None

    def __post_init__(self) -> None:
        if self.root_key == 0 and sys.platform == "win32":
            import winreg

            self.root_key = winreg.HKEY_CURRENT_USER

        if self.icon_path is None:
            default_ico = Path(__file__).resolve().parent.parent.parent / "assets" / "cuttle.ico"
            if default_ico.is_file():
                self.icon_path = default_ico


def get_default_cuttlectl_cmd() -> str:
    """Resolve default command string to execute cuttlectl."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        cuttlectl_exe = exe_dir / "cuttlectl.exe"
        if cuttlectl_exe.exists():
            return f'"{cuttlectl_exe}"'

    cuttlectl_on_path = shutil.which("cuttlectl")
    if cuttlectl_on_path:
        return f'"{cuttlectl_on_path}"'

    py_exec = sys.executable
    if sys.platform == "win32":
        candidate_pythonw = Path(sys.executable).with_name("pythonw.exe")
        if candidate_pythonw.is_file():
            py_exec = str(candidate_pythonw)

    return f'"{py_exec}" -m cuttle.worker.cuttlectl'


def get_default_manifest_path() -> Path:
    """Return default manifest file location in LocalAppData."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "Cuttle" / "installed_keys.json"


def delete_key_tree(root_key: Any, subkey: str) -> None:
    """Recursively delete a Windows registry key and all its child subkeys."""
    if sys.platform != "win32":
        return

    import winreg

    try:
        h = winreg.OpenKey(root_key, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("Failed to open key for deletion %s: %s", subkey, exc)
        return

    try:
        while True:
            try:
                child = winreg.EnumKey(h, 0)
                delete_key_tree(root_key, f"{subkey}\\{child}")
            except OSError:
                break
    finally:
        winreg.CloseKey(h)

    try:
        winreg.DeleteKey(root_key, subkey)
    except OSError as exc:
        logger.warning("Failed to delete key %s: %s", subkey, exc)


def install_context_menus(config: RegistryConfig | None = None) -> list[str]:
    """Register File Explorer cascading context menus for all supported formats.

    Dynamically queries Cuttle's conversion graph to generate verbs.
    Records all created root keys in the installation manifest.

    Returns the list of top-level created registry keys.
    """
    if sys.platform != "win32":
        logger.info("Registry context menus are only supported on Windows.")
        return []

    import winreg

    from cuttle.engine.graph import ConversionGraph
    from cuttle.engine.registry import load_registry

    cfg = config or RegistryConfig()
    cuttlectl = cfg.cuttlectl_cmd or get_default_cuttlectl_cmd()
    manifest_file = Path(cfg.manifest_path or get_default_manifest_path())

    reg = load_registry()
    graph = ConversionGraph(reg)

    from cuttle.engine.convert import get_available_tools

    avail_tools = get_available_tools()
    created_keys: list[str] = []

    for fmt_name, fmt_info in reg.formats.items():
        targets = graph.list_targets(fmt_name, available_tools=avail_tools)
        if not targets:
            continue

        # 1. Register subcommands container: Cuttle.menu.<fmt>
        menu_key_path = f"{cfg.base_path}\\Cuttle.menu.{fmt_name}"
        menu_shell_path = f"{menu_key_path}\\shell"
        created_keys.append(menu_key_path)

        for target in targets:
            target_verb_path = f"{menu_shell_path}\\{target.fmt}"
            target_command_path = f"{target_verb_path}\\command"

            if target.available:
                verb_label = f"Convert to {target.label}"
                cmd_str = f'{cuttlectl} "%1" {target.fmt}'
            elif target.missing == "libreoffice":
                verb_label = f"Convert to {target.label} (needs LibreOffice)"
                cmd_str = f"{cuttlectl} missing-tool libreoffice"
            else:
                verb_label = f"Convert to {target.label} (needs {target.missing})"
                cmd_str = f"{cuttlectl} missing-tool {target.missing}"

            # Create verb key
            k_verb = winreg.CreateKey(cfg.root_key, target_verb_path)
            winreg.SetValueEx(
                k_verb,
                "MUIVerb",
                0,
                winreg.REG_SZ,
                verb_label,
            )
            winreg.CloseKey(k_verb)

            # Create command key
            k_cmd = winreg.CreateKey(cfg.root_key, target_command_path)
            winreg.SetValueEx(k_cmd, "", 0, winreg.REG_SZ, cmd_str)
            winreg.CloseKey(k_cmd)

        # 2. Register file association for each extension under SystemFileAssociations
        for ext in fmt_info.ext:
            assoc_cuttle_path = f"{cfg.base_path}\\SystemFileAssociations\\.{ext}\\shell\\Cuttle"
            created_keys.append(assoc_cuttle_path)

            k_assoc = winreg.CreateKey(cfg.root_key, assoc_cuttle_path)
            winreg.SetValueEx(k_assoc, "MUIVerb", 0, winreg.REG_SZ, "Cuttle")
            winreg.SetValueEx(
                k_assoc,
                "ExtendedSubCommandsKey",
                0,
                winreg.REG_SZ,
                f"Cuttle.menu.{fmt_name}",
            )
            if cfg.icon_path:
                winreg.SetValueEx(
                    k_assoc,
                    "Icon",
                    0,
                    winreg.REG_SZ,
                    str(Path(cfg.icon_path).resolve()),
                )
            winreg.CloseKey(k_assoc)

    # Write audit manifest
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "version": "1.0",
        "base_path": cfg.base_path,
        "keys": created_keys,
    }
    manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    logger.info("Successfully registered %d context menu keys", len(created_keys))
    return created_keys


def uninstall_context_menus(config: RegistryConfig | None = None) -> int:
    """Remove all registered Explorer context menus recorded in the manifest.

    Returns the number of keys removed.
    """
    if sys.platform != "win32":
        return 0

    cfg = config or RegistryConfig()
    manifest_file = Path(cfg.manifest_path or get_default_manifest_path())

    if not manifest_file.exists():
        logger.warning("No installation manifest found at %s", manifest_file)
        return 0

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        keys = data.get("keys", [])
    except Exception as exc:
        logger.warning("Failed to parse manifest %s: %s", manifest_file, exc)
        return 0

    deleted_count = 0
    for key_path in keys:
        delete_key_tree(cfg.root_key, key_path)
        deleted_count += 1

    with contextlib.suppress(OSError):
        manifest_file.unlink()

    logger.info("Successfully uninstalled %d context menu keys", deleted_count)
    return deleted_count
