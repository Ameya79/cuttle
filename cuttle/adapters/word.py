"""Microsoft Word native conversion adapter for Windows.

Provides 100% pixel-perfect DOCX -> PDF conversion by utilizing Microsoft Word's
native rendering engine, preserving exact fonts, kerning, margins, and page counts.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)

# Concurrency lock: one Word COM export at a time to prevent resource contention
_WORD_LOCK = threading.Lock()


class WordAdapter(BaseAdapter):
    """Adapter for converting Word documents to PDF using native Microsoft Word."""

    name = "word"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Convert DOCX to PDF losslessly using native Microsoft Word."""
        if src_fmt.lower() == "docx" and dst_fmt.lower() == "pdf":
            return Quality.LOSSLESS
        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for DOCX to PDF via Microsoft Word."""
        if dst_fmt.lower() != "pdf":
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"Word adapter cannot convert to '{dst_fmt}'.",
                detail="Only PDF output is supported by Word adapter.",
            )

        args = ["word", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=None)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute DOCX to PDF conversion using Microsoft Word COM."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for Word conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before starting Word conversion.",
            )

        if sys.platform != "win32":
            raise CuttleError(
                code="E_TOOL_MISSING",
                user_message="Microsoft Word conversion is only supported on Windows.",
                detail=f"Operating system is '{sys.platform}', expected 'win32'.",
            )

        on_progress(10.0, "Waiting for Microsoft Word...")

        with _WORD_LOCK:
            if cancel.cancelled:
                raise CuttleError(
                    code="E_CANCELLED",
                    user_message="The conversion was cancelled.",
                    detail="Cancelled while queued for Word conversion.",
                )

            on_progress(30.0, "Rendering PDF with Microsoft Word...")

            try:
                from cuttle.platform.windows.word_com import convert_docx_to_pdf_word

                convert_docx_to_pdf_word(src, tmp_out, timeout_s=60.0)
            except TimeoutError as exc:
                raise CuttleError(
                    code="E_CONV_FAILED",
                    user_message=f"Conversion timed out for '{src.name}'.",
                    detail=str(exc),
                ) from exc
            except Exception as exc:
                if isinstance(exc, CuttleError):
                    raise
                raise CuttleError(
                    code="E_CONV_FAILED",
                    user_message=f"Microsoft Word failed to convert '{src.name}'.",
                    detail=str(exc),
                ) from exc

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled after Word PDF generation.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate output file opens with pypdf, has >= 1 page, and checks font metrics."""
        from cuttle.adapters.pdf import validate_pdf

        return validate_pdf(out, src_docx=src)
