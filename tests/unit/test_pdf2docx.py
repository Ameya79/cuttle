"""Unit tests for PDF to Word (DOCX) conversion adapter (P5-02).

Per TRD task card P5-02:
- Quality is always best_effort.
- Warning 'Tables and complex layouts may need touch ups.' is attached.
- Text PDF converts to a DOCX that opens cleanly.
- Scanned PDF without OCR raises E_UNSUPPORTED with a message offering OCR.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from cuttle.adapters.pdf2docx_adapter import WARNING_TOUCH_UPS, Pdf2DocxAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality
from cuttle.engine.validators import validate_office_document


def create_searchable_pdf(path: Path) -> Path:
    """Generate a minimal valid searchable PDF with extractable text."""
    text = "Cuttle PDF to Word conversion test. This document contains paragraphs of text."
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


def create_scanned_pdf(path: Path) -> Path:
    """Generate an image-only scanned PDF."""
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    img.save(path, format="PDF")
    return path


def test_can_convert_capabilities() -> None:
    """Pdf2DocxAdapter only converts PDF to DOCX at best_effort quality."""
    adapter = Pdf2DocxAdapter()
    assert adapter.can_convert("pdf", "docx") == Quality.BEST_EFFORT
    assert adapter.can_convert("pdf", "txt") is None
    assert adapter.can_convert("docx", "pdf") is None


def test_scanned_pdf_raises_e_unsupported_offering_ocr(tmp_path: Path) -> None:
    """Scanned PDF without OCR raises E_UNSUPPORTED mentioning OCR."""
    scanned_pdf = create_scanned_pdf(tmp_path / "scanned.pdf")
    adapter = Pdf2DocxAdapter()

    with pytest.raises(CuttleError) as exc_info:
        adapter.plan(scanned_pdf, "docx", tmp_path / "out.docx", {})

    err = exc_info.value
    assert err.code == "E_UNSUPPORTED"
    assert "OCR" in err.user_message


def test_searchable_pdf_converts_to_valid_docx(tmp_path: Path) -> None:
    """Searchable text PDF converts cleanly into a valid DOCX file."""
    text_pdf = create_searchable_pdf(tmp_path / "searchable.pdf")
    tmp_out = tmp_path / "converted.docx"
    adapter = Pdf2DocxAdapter()

    plan = adapter.plan(text_pdf, "docx", tmp_out, {})
    assert plan.args == ["pdf2docx", str(text_pdf), "docx", str(tmp_out)]

    progress_log: list[tuple[float | None, str]] = []

    def on_progress(p: float | None, msg: str) -> None:
        progress_log.append((p, msg))

    cancel = CancelToken()
    adapter.run(plan, on_progress=on_progress, cancel=cancel)

    assert tmp_out.is_file()
    assert tmp_out.stat().st_size > 0

    # Validate output DOCX structure
    val_res = adapter.validate(text_pdf, tmp_out)
    assert val_res.ok is True
    assert WARNING_TOUCH_UPS in val_res.warnings

    # Double check underlying office document validator
    raw_val = validate_office_document(tmp_out, expected_fmt="docx")
    assert raw_val.ok is True


def test_cancellation_honored(tmp_path: Path) -> None:
    """Pre-cancelled token immediately aborts conversion."""
    text_pdf = create_searchable_pdf(tmp_path / "searchable.pdf")
    tmp_out = tmp_path / "cancelled.docx"
    adapter = Pdf2DocxAdapter()
    plan = adapter.plan(text_pdf, "docx", tmp_out, {})

    cancel = CancelToken()
    cancel.cancel()

    with pytest.raises(CuttleError) as exc_info:
        adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)
    assert exc_info.value.code == "E_CANCELLED"
    assert not tmp_out.exists()
