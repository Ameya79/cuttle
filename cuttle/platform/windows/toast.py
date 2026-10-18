"""Native Windows 10/11 notification toasts for Cuttle.

Uses windows-toasts to deliver completion and error banners with interactive
action buttons ("Open File", "Show in Folder", "Copy Details").
Never raises exceptions out of notification calls: failures log and degrade gracefully.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def open_file(path: Path | str) -> bool:
    """Open a file with the default Windows application.

    Returns True if launched, False on error.
    """
    p = Path(path).resolve()
    if not p.exists():
        logger.warning("Cannot open non-existent file: %s", p)
        return False

    try:
        if sys.platform == "win32":
            os.startfile(str(p))
            return True
        return False
    except Exception as exc:
        logger.warning("Failed to open file %s: %s", p, exc)
        return False


def reveal_in_explorer(path: Path | str) -> bool:
    """Open Windows File Explorer with the specified file selected.

    Uses 'explorer /select,<path>' without shell=True.
    Returns True if launched, False on error.
    """
    p = Path(path).resolve()
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{p}"], shell=False)
            return True
        return False
    except Exception as exc:
        logger.warning("Failed to reveal file in explorer %s: %s", p, exc)
        return False


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the Windows clipboard via win32clipboard.

    Returns True if copied, False on error.
    """
    if sys.platform != "win32":
        return False

    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            return True
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:
        logger.warning("Failed to copy text to clipboard: %s", exc)
        return False


def notify_shell_file_created(path: Path | str) -> None:
    """Notify Windows Shell that a new file was created to instantly refresh Explorer views."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # SHCNE_CREATE = 0x00000002, SHCNF_PATHW = 0x0005
        ctypes.windll.shell32.SHChangeNotify(0x00000002, 0x0005, str(Path(path).resolve()), None)
    except Exception as exc:
        logger.debug("SHChangeNotify error: %s", exc)


class ToastNotifier:
    """Native Windows toast notification sender for Cuttle."""

    def __init__(self, app_id: str = "Cuttle") -> None:
        self.app_id = app_id
        self._toaster: Any = None
        if sys.platform == "win32":
            try:
                from windows_toasts import InteractableWindowsToaster

                self._toaster = InteractableWindowsToaster(app_id)
            except Exception as exc:
                logger.warning("Could not initialize InteractableWindowsToaster: %s", exc)

    def create_success_toast(
        self, output_path: Path | str, original_filename: str | None = None
    ) -> Any:
        """Construct the success Toast object with action buttons."""
        from windows_toasts import Toast, ToastButton

        p = Path(output_path).resolve()
        title = "Cuttle: Conversion Complete"
        body = f"{p.name} is ready!"
        toast = Toast([title, body])

        toast.AddAction(ToastButton("Open File", arguments="open"))
        toast.AddAction(ToastButton("Show in Folder", arguments="reveal"))

        def _on_activated(args: Any) -> None:
            arg = getattr(args, "arguments", "")
            if arg == "open":
                open_file(p)
            elif arg == "reveal":
                reveal_in_explorer(p)
            else:
                open_file(p)

        toast.on_activated = _on_activated
        return toast

    def create_error_toast(
        self,
        error_message: str,
        filename: str | None = None,
        detail: str | None = None,
    ) -> Any:
        """Construct the error Toast object with a Copy Details button."""
        from windows_toasts import Toast, ToastButton

        title = "Cuttle: Conversion Failed"
        body = f"{filename}: {error_message}" if filename else error_message
        toast = Toast([title, body])

        full_detail = detail or error_message
        toast.AddAction(ToastButton("Copy Details", arguments="copy"))

        def _on_activated(args: Any) -> None:
            arg = getattr(args, "arguments", "")
            if arg == "copy":
                copy_to_clipboard(full_detail)

        toast.on_activated = _on_activated
        return toast

    def notify_success(self, output_path: Path | str, original_filename: str | None = None) -> bool:
        """Display a native success toast notification.

        Returns True if dispatched to Windows, False if failed/disabled.
        """
        # Immediately tell Windows File Explorer to refresh and display the new file
        notify_shell_file_created(output_path)

        if self._toaster is None:
            return False

        try:
            toast = self.create_success_toast(output_path, original_filename)
            self._toaster.show_toast(toast)
            return True
        except Exception as exc:
            logger.warning("Failed to display success toast: %s", exc)
            return False

    def notify_error(
        self,
        error_message: str,
        filename: str | None = None,
        detail: str | None = None,
    ) -> bool:
        """Display a native error toast notification.

        Returns True if dispatched to Windows, False if failed/disabled.
        """
        if self._toaster is None:
            return False

        try:
            toast = self.create_error_toast(error_message, filename, detail)
            self._toaster.show_toast(toast)
            return True
        except Exception as exc:
            logger.warning("Failed to display error toast: %s", exc)
            return False


# Singleton instance and module helpers
_default_notifier: ToastNotifier | None = None


def get_notifier() -> ToastNotifier:
    """Return shared default ToastNotifier instance."""
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = ToastNotifier()
    return _default_notifier


def notify_success(output_path: Path | str, original_filename: str | None = None) -> bool:
    """Convenience helper to display a success toast via default notifier."""
    return get_notifier().notify_success(output_path, original_filename)


def notify_error(
    error_message: str,
    filename: str | None = None,
    detail: str | None = None,
) -> bool:
    """Convenience helper to display an error toast via default notifier."""
    return get_notifier().notify_error(error_message, filename, detail)
