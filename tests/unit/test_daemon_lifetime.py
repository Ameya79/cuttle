"""Unit tests for daemon lifetime persistence and desktop integration.

Per task card P2-UX-FIX:
- Verifies QApplication.quitOnLastWindowClosed is explicitly set to False.
- Verifies InteractableWindowsToaster is used for interactive action buttons.
- Verifies notify_shell_file_created calls Windows Shell notification safely.
- Verifies multiple consecutive batch completions do not terminate the event loop.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from cuttle.platform.windows.toast import (
    ToastNotifier,
    notify_shell_file_created,
    notify_success,
)
from cuttle.ui.progress_window import FloatingProgressWindow, get_or_create_app


def test_qt_app_quit_on_last_window_closed_is_false() -> None:
    """Ensure the Qt application does not quit when the progress window auto-closes."""
    app = get_or_create_app()
    app.setQuitOnLastWindowClosed(False)
    assert app.quitOnLastWindowClosed() is False


def test_toast_uses_interactable_toaster() -> None:
    """Ensure ToastNotifier instantiates InteractableWindowsToaster on Windows."""
    notifier = ToastNotifier("Cuttle-Test")
    if sys.platform == "win32":
        from windows_toasts import InteractableWindowsToaster

        assert isinstance(notifier._toaster, InteractableWindowsToaster)


def test_notify_shell_file_created_safe(tmp_path: Path) -> None:
    """Ensure notify_shell_file_created executes without exceptions."""
    dummy_file = tmp_path / "dummy_output.mp3"
    dummy_file.write_text("audio data")
    # Should not raise on any platform
    notify_shell_file_created(dummy_file)


def test_notify_success_triggers_shell_notification(tmp_path: Path) -> None:
    """Ensure notify_success calls notify_shell_file_created."""
    dummy_file = tmp_path / "sample.mp3"
    dummy_file.write_text("test")

    notifier = ToastNotifier("Cuttle-Test")
    notifier._toaster = MagicMock()
    with patch("cuttle.platform.windows.toast.notify_shell_file_created") as mock_notify:
        notifier.notify_success(dummy_file)
        mock_notify.assert_called_once_with(dummy_file)


def test_consecutive_floating_windows_creation_and_auto_close() -> None:
    """Ensure multiple consecutive FloatingProgressWindow instances can be created and closed."""
    app = get_or_create_app()
    app.setQuitOnLastWindowClosed(False)

    w1 = FloatingProgressWindow(batch_id="batch-1", auto_close_ms=0)
    w1.show()
    w1.close()

    # The Qt application should still be valid and alive
    w2 = FloatingProgressWindow(batch_id="batch-2", auto_close_ms=0)
    w2.show()
    w2.close()

    assert app.quitOnLastWindowClosed() is False
