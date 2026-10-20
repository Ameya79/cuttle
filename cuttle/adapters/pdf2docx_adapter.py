"""PDF to Word (DOCX) conversion adapter using pdf2docx.

Per TRD task card P5-02:
- Quality is always best_effort.
- Adds warning: 'Tables and complex layouts may need touch ups.'
- Text PDF converts to a DOCX that opens cleanly.
- Scanned PDF without OCR raises E_UNSUPPORTED with a message offering OCR.
"""

from __future__ import annotations

from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.pdf import is_scanned_pdf
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)
from cuttle.engine.validators import validate_office_document

WARNING_TOUCH_UPS = "Tables and complex layouts may need touch ups."


class Pdf2DocxAdapter(BaseAdapter):
    """Adapter for converting searchable PDF documents to Microsoft Word (DOCX)."""

    name = "pdf2docx"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """PDF to Word conversion is supported with best_effort quality."""
        if src_fmt.lower() == "pdf" and dst_fmt.lower() == "docx":
            return Quality.BEST_EFFORT
        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for PDF to DOCX."""
        if dst_fmt.lower() != "docx":
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"pdf2docx adapter cannot convert to '{dst_fmt}'.",
                detail="Only .docx output is supported by pdf2docx.",
            )

        password = options.get("password")
        if is_scanned_pdf(src, password=password):
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=(
                    "This PDF appears to be a scanned document without text. "
                    "Run OCR before converting to Word."
                ),
                detail=(
                    f"Scanned PDF detected in '{src.name}'. "
                    "Run OCR first to recognize text before Word conversion."
                ),
            )

        args = ["pdf2docx", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=None)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute PDF to Word conversion using pdf2docx."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for PDF to Word conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before starting PDF to Word conversion.",
            )

        try:
            from pdf2docx import Converter
        except ImportError as exc:
            raise CuttleError(
                code="E_TOOL_MISSING",
                user_message="The pdf2docx library is required for PDF to Word conversion.",
                detail=str(exc),
            ) from exc

        on_progress(10.0, "Parsing PDF pages...")

        try:
            cv = Converter(str(src))
            try:
                on_progress(30.0, "Converting layout and content...")
                if cancel.cancelled:
                    raise CuttleError(
                        code="E_CANCELLED",
                        user_message="The conversion was cancelled.",
                        detail="Cancelled during PDF to Word conversion.",
                    )

                cv.convert(str(tmp_out), delete_end_line_hyphen=True)
                on_progress(95.0, "Finalizing Word document...")
            finally:
                cv.close()
        except Exception as exc:
            if isinstance(exc, CuttleError):
                raise
            raise CuttleError(
                code="E_CONV_FAILED",
                user_message=f"Failed to convert '{src.name}' to Word.",
                detail=str(exc),
            ) from exc

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled after DOCX generation.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate that the generated DOCX is a well-formed Word document."""
        res = validate_office_document(out, expected_fmt="docx")
        if not res.ok:
            return res

        warnings = list(res.warnings)
        warnings.append(WARNING_TOUCH_UPS)
        return ValidationResult(ok=True, warnings=warnings)
