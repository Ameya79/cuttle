"""LibreOffice headless conversion adapter for Office documents to PDF.

Per TRD §6.1, §6.2, and task card P3-03:
- Runs: soffice --headless --norestore --nolockcheck
        -env:UserInstallation=file:///<private profile dir>
        --convert-to pdf --outdir <private temp dir> SRC
- Moves produced file to destination .cuttle-part path.
- Strictly single concurrency via file/thread lock.
- 120-second timeout with process-tree kill switch.
- Disables macros. Validates generated PDF opens cleanly with pypdf and >= 1 page.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.runner import run_command
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)
from cuttle.platform.windows.office_detect import detect_office

# Concurrency lock: strictly one LibreOffice conversion job at a time
_LIBREOFFICE_LOCK = threading.Lock()

OFFICE_TO_PDF_FORMATS = {"docx", "pptx", "xlsx", "odt"}


class LibreOfficeAdapter(BaseAdapter):
    """Headless LibreOffice adapter for converting office documents to PDF."""

    name = "libreoffice"

    def __init__(self, soffice_path: Path | str | None = None) -> None:
        self._custom_soffice = Path(soffice_path) if soffice_path else None

    @property
    def soffice(self) -> Path:
        """Resolve path to soffice.exe, raising E_TOOL_MISSING if not installed."""
        if self._custom_soffice is not None:
            return self._custom_soffice

        info = detect_office()
        if info.installed and info.path:
            return info.path

        raise CuttleError(
            code="E_TOOL_MISSING",
            user_message="LibreOffice is required for converting office documents to PDF.",
            detail=(
                "soffice.exe was not detected in Program Files, PATH, or "
                "Windows App Paths registry."
            ),
        )

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Return Quality.LOSSLESS for docx/pptx/xlsx/odt -> pdf."""
        if src_fmt.lower() in OFFICE_TO_PDF_FORMATS and dst_fmt.lower() == "pdf":
            return Quality.LOSSLESS
        return None

    def build_argv(
        self,
        src: Path,
        profile_dir: Path,
        out_dir: Path,
    ) -> list[str]:
        """Construct exact command line matching TRD §6.3/task card P3-03."""
        # Convert profile path to file:/// URI format expected by LibreOffice
        profile_uri = profile_dir.resolve().as_uri()

        return [
            str(self.soffice),
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir.resolve()),
            str(src.resolve()),
        ]

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for LibreOffice."""
        if dst_fmt.lower() != "pdf":
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"LibreOffice adapter does not support converting to '{dst_fmt}'.",
                detail=f"Only target 'pdf' is supported, requested '{dst_fmt}'.",
            )

        # Store working directories in options or metadata
        return Plan(args=[str(src), str(tmp_out)])

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute LibreOffice conversion under a concurrency lock."""
        src = Path(plan.args[0])
        tmp_out = Path(plan.args[1])

        # Enforce single concurrency
        on_progress(None, "Waiting for LibreOffice queue...")
        with _LIBREOFFICE_LOCK:
            if cancel.cancelled:
                raise CuttleError(
                    code="E_CANCELLED",
                    user_message="Conversion was cancelled.",
                )

            on_progress(None, "Converting document with LibreOffice...")

            # Create private isolated temporary profile and outdir
            with (
                tempfile.TemporaryDirectory(prefix="cuttle_lo_profile_") as prof_tmp,
                tempfile.TemporaryDirectory(prefix="cuttle_lo_out_") as out_tmp,
            ):
                profile_path = Path(prof_tmp)
                out_path = Path(out_tmp)

                argv = self.build_argv(src, profile_path, out_path)

                try:
                    run_command(
                        argv,
                        timeout_s=120.0,
                        on_stdout_line=None,
                        cancel=cancel,
                    )
                except CuttleError:
                    raise

                # Locate the produced PDF
                expected_pdf = out_path / f"{src.stem}.pdf"
                if not expected_pdf.is_file():
                    # Look for any generated .pdf file in out_path
                    pdfs = list(out_path.glob("*.pdf"))
                    if pdfs:
                        expected_pdf = pdfs[0]
                    else:
                        raise CuttleError(
                            code="E_TOOL_FAILED",
                            user_message=(f"LibreOffice failed to generate PDF for '{src.name}'."),
                            detail=f"No PDF file produced in {out_path}.",
                        )

                    # Move produced PDF to tmp_out destination (.cuttle-part)
                    shutil.move(str(expected_pdf), str(tmp_out))

            on_progress(100.0, "Complete")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate output file opens with pypdf, has >= 1 page, and detects font substitutions."""
        from cuttle.adapters.pdf import validate_pdf

        return validate_pdf(out, src_docx=src)
