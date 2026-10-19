"""Unit tests for OCR pipeline and tool detection (P5-03).

Per TRD task card P5-03:
- Detects Tesseract and OCRmyPDF as add-ons.
- Missing tools give a clear E_TOOL_MISSING message.
- Executes OCR first, then converts via pdf2docx.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from cuttle.adapters.ocr import (
    WARNING_OCR_QUALITY,
    OcrAdapter,
    detect_ocrmypdf,
    detect_tesseract,
    run_ocr,
)
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality
from cuttle.engine.validators import validate_office_document


def create_scanned_pdf(path: Path) -> Path:
    """Create an image-only scanned PDF."""
    img = Image.new("RGB", (200, 200), color=(80, 120, 160))
    img.save(path, format="PDF")
    return path


def create_searchable_pdf(path: Path) -> Path:
    """Create a searchable PDF with text stream."""
    text = "OCR recognized text content test document."
    stream_content = f"BT\n/F1 12 Tf\n50 250 Td\n({text}) Tj\nET\n".encode("latin1")
    length = len(stream_content)

    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length "
        + str(length).encode("ascii")
        + b" >>\nstream\n"
        + stream_content
        + b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n500\n%%EOF\n"
    )
    path.write_bytes(pdf_bytes)
    return path


def test_ocr_tool_detection_defaults() -> None:
    """Tool detection returns strings or None without unhandled exceptions."""
    tess = detect_tesseract()
    assert tess is None or isinstance(tess, str)

    ocr_pdf = detect_ocrmypdf()
    assert ocr_pdf is None or isinstance(ocr_pdf, str)


def test_missing_ocr_tool_raises_clear_e_tool_missing(tmp_path: Path) -> None:
    """When neither tool is found, run_ocr raises E_TOOL_MISSING with clear message."""
    src = create_scanned_pdf(tmp_path / "scanned.pdf")
    out = tmp_path / "searchable.pdf"

    with patch("cuttle.adapters.ocr.get_available_ocr_tool", return_value=None):
        with pytest.raises(CuttleError) as exc_info:
            run_ocr(src, out)

        err = exc_info.value
        assert err.code == "E_TOOL_MISSING"
        assert "Tesseract or OCRmyPDF" in err.user_message


def test_ocr_adapter_capabilities() -> None:
    """OcrAdapter supports PDF to DOCX and PDF to PDF at best_effort quality."""
    adapter = OcrAdapter()
    assert adapter.can_convert("pdf", "docx") == Quality.BEST_EFFORT
    assert adapter.can_convert("pdf", "pdf") == Quality.BEST_EFFORT
    assert adapter.can_convert("pdf", "mp3") is None


def test_ocr_pipeline_to_docx(tmp_path: Path) -> None:
    """OcrAdapter runs OCR stage first, then delegates to pdf2docx."""
    src = create_scanned_pdf(tmp_path / "invoice_scanned.pdf")
    tmp_out = tmp_path / "invoice_recognized.docx"
    adapter = OcrAdapter()

    plan = adapter.plan(src, "docx", tmp_out, {})
    assert plan.args == ["ocr", str(src), "docx", str(tmp_out)]

    # Mock run_ocr to simulate OCR producing a searchable PDF
    def mock_run_ocr(source: Path, target: Path, **kwargs: object) -> None:
        create_searchable_pdf(target)

    with patch("cuttle.adapters.ocr.run_ocr", side_effect=mock_run_ocr):
        cancel = CancelToken()
        adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)

    assert tmp_out.is_file()
    assert tmp_out.stat().st_size > 0

    # Validate output DOCX structure and warnings
    val_res = adapter.validate(src, tmp_out)
    assert val_res.ok is True
    assert WARNING_OCR_QUALITY in val_res.warnings

    raw_val = validate_office_document(tmp_out, expected_fmt="docx")
    assert raw_val.ok is True


def test_ocr_cancellation_honored(tmp_path: Path) -> None:
    """Pre-cancelled token immediately aborts OCR execution."""
    src = create_scanned_pdf(tmp_path / "scanned.pdf")
    tmp_out = tmp_path / "out.docx"
    adapter = OcrAdapter()
    plan = adapter.plan(src, "docx", tmp_out, {})

    cancel = CancelToken()
    cancel.cancel()

    with pytest.raises(CuttleError) as exc_info:
        adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)

    assert exc_info.value.code == "E_CANCELLED"
    assert not tmp_out.exists()
