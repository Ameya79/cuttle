"""Microsoft Word COM automation for Windows.

Provides high-fidelity, native Word document conversions (e.g. DOCX -> PDF)
by automating Word via COM DispatchEx with zero UI prompts.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# WdSaveFormat constant for PDF
WD_FORMAT_PDF = 17
# WdSaveOptions constant for closing without saving changes to source
WD_DO_NOT_SAVE_CHANGES = 0
# WdAlertLevel constant for suppressing all dialogs/prompts
WD_ALERTS_NONE = 0


def convert_docx_to_pdf_word(
    src: Path,
    dst: Path,
    timeout_s: float = 60.0,
) -> None:
    """Convert a DOCX file to PDF using Microsoft Word COM automation.

    Parameters:
        src: Path to input DOCX document.
        dst: Path where output PDF document will be written.
        timeout_s: Maximum execution duration before timing out.

    Raises:
        RuntimeError: If not on Windows or COM automation fails.
    """
    if sys.platform != "win32":
        raise RuntimeError("Word COM automation is only supported on Windows.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as err:
        raise RuntimeError("pywin32 is required for Word COM automation.") from err

    abs_src = str(src.resolve())
    abs_dst = str(dst.resolve())

    # Ensure COM is initialized on the current thread
    pythoncom.CoInitialize()
    word = None
    doc = None
    start_time = time.monotonic()

    try:
        # Create an isolated Word instance (DispatchEx) so user documents are untouched
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE

        # Open source document read-only and hidden
        doc = word.Documents.Open(
            abs_src,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
            ConfirmConversions=False,
        )

        if time.monotonic() - start_time > timeout_s:
            raise TimeoutError(f"Word conversion timed out after {timeout_s}s.")

        # Save document as PDF (17 = wdFormatPDF)
        doc.SaveAs2(
            abs_dst,
            FileFormat=WD_FORMAT_PDF,
        )

        if not dst.is_file() or dst.stat().st_size == 0:
            raise RuntimeError(f"Word completed but output file '{dst}' is missing or empty.")

    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception as close_err:
                logger.warning("Failed to close Word document cleanly: %s", close_err)
            doc = None

        if word is not None:
            try:
                word.Quit(SaveChanges=WD_DO_NOT_SAVE_CHANGES)
            except Exception as quit_err:
                logger.warning("Failed to quit Word application cleanly: %s", quit_err)
            word = None

        with contextlib.suppress(Exception):
            pythoncom.CoUninitialize()
