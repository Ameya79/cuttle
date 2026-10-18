"""Unit tests for cuttle/shell/registry_installer.py File Explorer context menus.

Runs inside an isolated HKCU\\Software\\CuttleTest sandbox hive to ensure
real system file associations are never touched or modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cuttle.shell.registry_installer import (
    RegistryConfig,
    delete_key_tree,
    get_default_cuttlectl_cmd,
    get_default_manifest_path,
    install_context_menus,
    uninstall_context_menus,
)

SANDBOX_BASE = r"Software\CuttleTest\Classes"


@pytest.fixture(autouse=True)
def cleanup_sandbox() -> None:
    """Ensure sandbox test registry key is cleaned up before and after each test."""
    if sys.platform == "win32":
        import winreg

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\CuttleTest")
    yield
    if sys.platform == "win32":
        import winreg

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\CuttleTest")


def test_default_paths_and_config() -> None:
    cfg = RegistryConfig()
    assert cfg.base_path == r"Software\Classes"
    assert get_default_cuttlectl_cmd()
    assert get_default_manifest_path().name == "installed_keys.json"


def test_delete_key_tree_nonexistent() -> None:
    if sys.platform == "win32":
        import winreg

        # Should silently succeed
        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\CuttleTest\NonExistent")


def test_install_and_uninstall_in_sandbox(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Registry context menus are Windows only")

    import winreg

    manifest = tmp_path / "installed_keys.json"
    dummy_icon = tmp_path / "cuttle.ico"
    dummy_icon.write_text("icon")

    cfg = RegistryConfig(
        base_path=SANDBOX_BASE,
        cuttlectl_cmd=r'"C:\Program Files\Cuttle\cuttlectl.exe"',
        icon_path=dummy_icon,
        manifest_path=manifest,
    )

    # 1. Install
    created = install_context_menus(cfg)
    assert len(created) > 0
    assert manifest.exists()

    # Verify manifest content
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["base_path"] == SANDBOX_BASE
    assert len(manifest_data["keys"]) == len(created)

    # Check MP4 root association key
    mp4_assoc_path = f"{SANDBOX_BASE}\\SystemFileAssociations\\.mp4\\shell\\Cuttle"
    k_assoc = winreg.OpenKey(winreg.HKEY_CURRENT_USER, mp4_assoc_path)
    try:
        mui, _ = winreg.QueryValueEx(k_assoc, "MUIVerb")
        assert mui == "Cuttle"
        ext_key, _ = winreg.QueryValueEx(k_assoc, "ExtendedSubCommandsKey")
        assert ext_key == "Cuttle.menu.mp4"
        icon_val, _ = winreg.QueryValueEx(k_assoc, "Icon")
        assert str(dummy_icon.resolve()) in icon_val
    finally:
        winreg.CloseKey(k_assoc)

    # Check MP4 -> MP3 subcommands verb & command
    mp3_cmd_path = f"{SANDBOX_BASE}\\Cuttle.menu.mp4\\shell\\mp3\\command"
    k_cmd = winreg.OpenKey(winreg.HKEY_CURRENT_USER, mp3_cmd_path)
    try:
        cmd_str, _ = winreg.QueryValueEx(k_cmd, "")
        assert cmd_str == '"C:\\Program Files\\Cuttle\\cuttlectl.exe" "%1" mp3'
    finally:
        winreg.CloseKey(k_cmd)

    # 2. Uninstall
    deleted_count = uninstall_context_menus(cfg)
    assert deleted_count == len(created)
    assert not manifest.exists()

    # Verify keys are completely removed
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, mp4_assoc_path)

    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, f"{SANDBOX_BASE}\\Cuttle.menu.mp4")


def test_uninstall_missing_or_corrupt_manifest(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Registry context menus are Windows only")

    # Missing manifest
    missing_manifest = tmp_path / "missing.json"
    cfg = RegistryConfig(manifest_path=missing_manifest)
    assert uninstall_context_menus(cfg) == 0

    # Corrupted manifest
    corrupt_manifest = tmp_path / "corrupt.json"
    corrupt_manifest.write_text("{invalid json")
    cfg_corrupt = RegistryConfig(manifest_path=corrupt_manifest)
    assert uninstall_context_menus(cfg_corrupt) == 0


def test_idempotent_install_in_sandbox(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Registry context menus are Windows only")

    manifest = tmp_path / "installed_keys.json"
    cfg = RegistryConfig(
        base_path=SANDBOX_BASE,
        cuttlectl_cmd=r'"C:\Program Files\Cuttle\cuttlectl.exe"',
        icon_path=None,
        manifest_path=manifest,
    )

    created1 = install_context_menus(cfg)
    created2 = install_context_menus(cfg)
    assert len(created1) == len(created2)

    deleted = uninstall_context_menus(cfg)
    assert deleted == len(created2)
