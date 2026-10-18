"""Unit tests for settings and system tray icon in cuttle/worker/."""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cuttle.worker.settings import (
    CuttleSettings,
    default_max_jobs,
    get_default_settings_path,
    get_default_worker_cmd,
    is_autostart_enabled,
    load_settings,
    save_settings,
    set_autostart_enabled,
)

# Force offscreen for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_default_settings() -> None:
    s = CuttleSettings()
    assert s.output_dir is None
    assert s.max_parallel_jobs == default_max_jobs()
    assert s.autostart is True
    assert s.notifications_enabled is True
    assert s.collision_suffix == "(converted)"
    assert get_default_settings_path().name == "settings.toml"
    assert get_default_worker_cmd()


def test_save_and_load_settings(tmp_path: Path) -> None:
    settings_file = tmp_path / "custom_settings.toml"
    custom_dir = tmp_path / "custom_output"

    original = CuttleSettings(
        output_dir=custom_dir,
        max_parallel_jobs=4,
        autostart=False,
        notifications_enabled=False,
        collision_suffix="(custom)",
    )

    saved_path = save_settings(original, settings_file)
    assert saved_path == settings_file
    assert settings_file.is_file()

    loaded = load_settings(settings_file)
    assert loaded.output_dir == custom_dir
    assert loaded.max_parallel_jobs == 4
    assert loaded.autostart is False
    assert loaded.notifications_enabled is False
    assert loaded.collision_suffix == "(custom)"


def test_corrupt_and_missing_settings(tmp_path: Path) -> None:
    # Missing file returns defaults
    missing = tmp_path / "missing.toml"
    s_missing = load_settings(missing)
    assert s_missing == CuttleSettings()

    # Corrupt file returns defaults
    corrupt = tmp_path / "corrupt.toml"
    corrupt.write_text("invalid = = toml [}")
    s_corrupt = load_settings(corrupt)
    assert s_corrupt == CuttleSettings()


def test_autostart_registry_sandbox() -> None:
    if sys.platform != "win32":
        pytest.skip("Autostart registry test is Windows only")

    import winreg

    sandbox_run = r"Software\CuttleTest\Run"

    # Clean up before
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sandbox_run, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(k, "Cuttle")
        winreg.CloseKey(k)
    except OSError:
        pass

    try:
        # Initially disabled
        assert not is_autostart_enabled(run_key_base=sandbox_run)

        # Enable autostart
        assert set_autostart_enabled(
            True,
            run_key_base=sandbox_run,
            app_cmd=r'"C:\Program Files\Cuttle\cuttle-worker.exe"',
        )
        assert is_autostart_enabled(run_key_base=sandbox_run)

        # Verify registry entry
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sandbox_run, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(k, "Cuttle")
            assert val == r'"C:\Program Files\Cuttle\cuttle-worker.exe"'
        finally:
            winreg.CloseKey(k)

        # Disable autostart
        assert set_autostart_enabled(False, run_key_base=sandbox_run)
        assert not is_autostart_enabled(run_key_base=sandbox_run)

    finally:
        # Clean up after
        with contextlib.suppress(OSError):
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sandbox_run)


def test_tray_icon_and_menu(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from cuttle.worker.tray import CuttleTrayIcon

    app = QApplication.instance() or QApplication([])
    _ = app

    dummy_ico = tmp_path / "app.ico"
    dummy_ico.write_text("icon")

    tray = CuttleTrayIcon(icon_path=dummy_ico)
    assert tray.toolTip() == "Cuttle: Idle"
    assert tray.action_header.text() == "Cuttle: Idle"

    # Status updates
    tray.update_status(3, 1)
    assert tray.toolTip() == "Cuttle: 3 converting, 1 queued"
    assert tray.action_header.text() == "Cuttle: 3 converting, 1 queued"

    tray.update_status(0, 0)
    assert tray.toolTip() == "Cuttle: Idle"

    # Test signal triggers
    mock_quit = MagicMock()
    mock_settings = MagicMock()
    mock_output = MagicMock()

    tray.quit_requested.connect(mock_quit)
    tray.settings_requested.connect(mock_settings)
    tray.open_output_requested.connect(mock_output)

    tray.action_quit.trigger()
    mock_quit.assert_called_once()

    tray.action_settings.trigger()
    mock_settings.assert_called_once()

    tray.action_open_output.trigger()
    mock_output.assert_called_once()
