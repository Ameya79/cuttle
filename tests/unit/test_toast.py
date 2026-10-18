"""Unit tests for cuttle/platform/windows/toast.py Windows native toasts."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cuttle.platform.windows.toast import (
    ToastNotifier,
    copy_to_clipboard,
    get_notifier,
    notify_error,
    notify_success,
    open_file,
    reveal_in_explorer,
)


def test_open_file_missing_returns_false(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.mp3"
    assert not open_file(missing)


def test_open_file_calls_startfile(tmp_path: Path) -> None:
    existing = tmp_path / "sample.mp3"
    existing.write_text("audio content")

    if sys.platform == "win32":
        with patch("os.startfile", MagicMock()) as mock_start:
            assert open_file(existing) is True
            mock_start.assert_called_once_with(str(existing.resolve()))
    else:
        assert open_file(existing) is False


def test_open_file_handles_exception(tmp_path: Path) -> None:
    existing = tmp_path / "sample.mp3"
    existing.write_text("audio content")

    if sys.platform == "win32":
        with patch("os.startfile", side_effect=OSError("Access denied")):
            assert open_file(existing) is False


def test_reveal_in_explorer_calls_popen(tmp_path: Path) -> None:
    p = tmp_path / "output.mp4"
    p.write_text("video")

    with patch("subprocess.Popen") as mock_popen:
        result = reveal_in_explorer(p)
        if sys.platform == "win32":
            assert result is True
            mock_popen.assert_called_once_with(["explorer", f"/select,{p.resolve()}"], shell=False)
        else:
            assert result is False


def test_reveal_in_explorer_handles_exception(tmp_path: Path) -> None:
    p = tmp_path / "output.mp4"
    if sys.platform == "win32":
        with patch("subprocess.Popen", side_effect=OSError("Explorer crash")):
            assert reveal_in_explorer(p) is False


def test_copy_to_clipboard() -> None:
    if sys.platform == "win32":
        test_text = "Diagnostic Error Code: E_TOOL_FAILED"
        assert copy_to_clipboard(test_text) is True
        # Verify from clipboard
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            assert data == test_text
        finally:
            win32clipboard.CloseClipboard()
    else:
        assert copy_to_clipboard("test") is False


def test_create_success_toast(tmp_path: Path) -> None:
    notifier = ToastNotifier()
    out = tmp_path / "converted.mp3"
    out.write_text("audio")

    toast = notifier.create_success_toast(out)
    assert "Cuttle: Conversion Complete" in toast.text_fields[0]
    assert "converted.mp3 is ready!" in toast.text_fields[1]
    assert len(toast.actions) == 2
    assert toast.actions[0].content == "Open File"
    assert toast.actions[0].arguments == "open"
    assert toast.actions[1].content == "Show in Folder"
    assert toast.actions[1].arguments == "reveal"

    # Test activation callbacks
    with patch("cuttle.platform.windows.toast.open_file") as mock_open:
        toast.on_activated(SimpleNamespace(arguments="open"))
        mock_open.assert_called_once_with(out.resolve())

    with patch("cuttle.platform.windows.toast.reveal_in_explorer") as mock_reveal:
        toast.on_activated(SimpleNamespace(arguments="reveal"))
        mock_reveal.assert_called_once_with(out.resolve())


def test_create_error_toast() -> None:
    notifier = ToastNotifier()
    toast = notifier.create_error_toast("Disk full", filename="clip.mp4", detail="No space left")

    assert "Cuttle: Conversion Failed" in toast.text_fields[0]
    assert "clip.mp4: Disk full" in toast.text_fields[1]
    assert len(toast.actions) == 1
    assert toast.actions[0].content == "Copy Details"
    assert toast.actions[0].arguments == "copy"

    with patch("cuttle.platform.windows.toast.copy_to_clipboard") as mock_copy:
        toast.on_activated(SimpleNamespace(arguments="copy"))
        mock_copy.assert_called_once_with("No space left")


def test_notify_methods_graceful_on_error(tmp_path: Path) -> None:
    notifier = ToastNotifier()
    out = tmp_path / "sample.mp3"

    # If toaster is None
    notifier._toaster = None
    assert notifier.notify_success(out) is False
    assert notifier.notify_error("Error") is False

    # If toaster raises an exception
    mock_toaster = MagicMock()
    mock_toaster.show_toast.side_effect = RuntimeError("Windows Notification Service stopped")
    notifier._toaster = mock_toaster

    assert notifier.notify_success(out) is False
    assert notifier.notify_error("Error") is False


def test_module_helpers(tmp_path: Path) -> None:
    out = tmp_path / "sample.mp3"
    out.write_text("ok")

    notifier = get_notifier()
    assert isinstance(notifier, ToastNotifier)

    with patch.object(notifier, "notify_success", return_value=True) as mock_s:
        assert notify_success(out) is True
        mock_s.assert_called_once_with(out, None)

    with patch.object(notifier, "notify_error", return_value=True) as mock_e:
        assert notify_error("Failed", filename="test.mov") is True
        mock_e.assert_called_once_with("Failed", "test.mov", None)
