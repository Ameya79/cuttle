"""OCR conversion adapter and tool detector for scanned PDFs (P5-03).

Per TRD task card P5-03:
- Detects Tesseract and OCRmyPDF as add-ons.
- Missing tools give a clear E_TOOL_MISSING message.
- Executes OCR pipeline first, then converts via pdf2docx.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.pdf import validate_pdf
from cuttle.engine.errors import CuttleError
from cuttle.engine.runner import run_command
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)
from cuttle.engine.validators import validate_office_document

WARNING_OCR_QUALITY = "Text recognized via OCR. Layout, formatting, and characters may need review."


def detect_tesseract() -> str | None:
    """Locate Tesseract-OCR binary on PATH or standard Windows installation locations."""
    # 1. System PATH
    found = shutil.which("tesseract")
    if found:
        return found

    # 2. Well-known Windows paths
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Tesseract-OCR"
        / "tesseract.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Tesseract-OCR"
        / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)

    return None


def detect_ocrmypdf() -> str | None:
    """Locate OCRmyPDF executable on PATH or in current Python environment scripts."""
    found = shutil.which("ocrmypdf")
    if found:
        return found

    # Check python virtual environment scripts directory
    venv_script = (
        Path(__file__).resolve().parent.parent.parent / ".venv" / "Scripts" / "ocrmypdf.exe"
    )
    if venv_script.is_file():
        return str(venv_script)

    return None


def get_available_ocr_tool() -> tuple[str, str] | None:
    """Return the preferred available OCR engine: ('ocrmypdf', path) or ('tesseract', path)."""
    ocrmypdf_bin = detect_ocrmypdf()
    if ocrmypdf_bin:
        return ("ocrmypdf", ocrmypdf_bin)

    tesseract_bin = detect_tesseract()
    if tesseract_bin:
        return ("tesseract", tesseract_bin)

    return None


def run_ocr(
    src_pdf: Path,
    out_searchable_pdf: Path,
    cancel: CancelToken | None = None,
    on_progress: ProgressCb | None = None,
    custom_tool: tuple[str, str] | None = None,
) -> None:
    """Execute OCR on a scanned PDF to produce a searchable PDF."""
    tool_info = custom_tool or get_available_ocr_tool()
    if not tool_info:
        raise CuttleError(
            code="E_TOOL_MISSING",
            user_message=(
                "OCR tools (Tesseract or OCRmyPDF) are required for scanned PDF "
                "recognition but were not found."
            ),
            detail=(
                "Neither 'tesseract' nor 'ocrmypdf' was found on your system. "
                "Install Tesseract-OCR or OCRmyPDF to enable text extraction "
                "from scanned documents."
            ),
        )

    tool_type, tool_path = tool_info

    if cancel and cancel.cancelled:
        raise CuttleError(
            code="E_CANCELLED",
            user_message="The conversion was cancelled.",
            detail="Cancelled before OCR started.",
        )

    if on_progress:
        on_progress(10.0, f"Running OCR recognition with {tool_type}...")

    if tool_type == "ocrmypdf":
        argv = [
            tool_path,
            "--skip-text",
            "--clean",
            str(src_pdf),
            str(out_searchable_pdf),
        ]
        run_command(argv, timeout_s=300, cancel=cancel)
    elif tool_type == "tesseract":
        # Tesseract outputs to base_name.pdf when output format 'pdf' is passed
        out_base = out_searchable_pdf.with_suffix("")
        argv = [
            tool_path,
            str(src_pdf),
            str(out_base),
            "pdf",
        ]
        run_command(argv, timeout_s=300, cancel=cancel)
        # Ensure target file exists if tesseract named it out_base.pdf
        generated_pdf = out_base.with_suffix(".pdf")
        if generated_pdf.is_file() and generated_pdf != out_searchable_pdf:
            shutil.move(str(generated_pdf), str(out_searchable_pdf))

    if on_progress:
        on_progress(100.0, "OCR recognition completed.")


class OcrAdapter(BaseAdapter):
    """Adapter for OCR text extraction and conversion of scanned PDFs."""

    name = "ocr"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """OCR converts scanned PDF into Word (DOCX) or searchable PDF."""
        if src_fmt.lower() == "pdf" and dst_fmt.lower() in ("docx", "pdf"):
            return Quality.BEST_EFFORT
        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct OCR conversion plan."""
        args = ["ocr", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=15.0)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute OCR processing, chaining to pdf2docx if output is DOCX."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for OCR conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        dst_fmt = plan.args[2].lower()
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before OCR execution.",
            )

        if dst_fmt == "docx":
            # 1. Run OCR to produce an intermediate searchable PDF
            with tempfile.TemporaryDirectory() as td:
                temp_searchable_pdf = Path(td) / f"{src.stem}_searchable.pdf"
                on_progress(20.0, "Recognizing text with OCR...")
                run_ocr(src, temp_searchable_pdf, cancel=cancel, on_progress=on_progress)

                if cancel.cancelled:
                    raise CuttleError(
                        code="E_CANCELLED",
                        user_message="The conversion was cancelled.",
                        detail="Cancelled after OCR text recognition.",
                    )

                # 2. Run P5-02 pdf2docx on the generated searchable PDF
                on_progress(60.0, "Converting recognized document to Word (DOCX)...")
                from cuttle.adapters.pdf2docx_adapter import Pdf2DocxAdapter

                p2d_adapter = Pdf2DocxAdapter()
                sub_plan = p2d_adapter.plan(temp_searchable_pdf, "docx", tmp_out, {})
                p2d_adapter.run(sub_plan, on_progress=on_progress, cancel=cancel)
        elif dst_fmt == "pdf":
            # Direct OCR to produce searchable PDF
            run_ocr(src, tmp_out, cancel=cancel, on_progress=on_progress)
        else:
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"OCR adapter does not support output format '{dst_fmt}'.",
                detail=f"Requested format: '{dst_fmt}'.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate OCR output format."""
        if out.suffix.lower() == ".docx":
            res = validate_office_document(out, expected_fmt="docx")
            if not res.ok:
                return res
            warnings = list(res.warnings)
            warnings.append(WARNING_OCR_QUALITY)
            return ValidationResult(ok=True, warnings=warnings)

        if out.suffix.lower() == ".pdf":
            res = validate_pdf(out)
            if not res.ok:
                return res
            warnings = list(res.warnings)
            warnings.append(WARNING_OCR_QUALITY)
            return ValidationResult(ok=True, warnings=warnings)

        return ValidationResult(ok=True)
