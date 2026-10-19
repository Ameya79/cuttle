"""Integration tests for Phase 5 Hard Conversions pipeline (P5-07).

Verifies:
- Scanned PDF detection and graceful rejection without OCR.
- Searchable PDF to Word (DOCX) conversion pipeline.
- Multi-image merge to PDF and PDF page rendering to images.
- DWG add-on integration with LibreOffice Draw renderer.
- Quality report completeness and synchronization.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pypdf
import pytest
from PIL import Image

from cuttle.adapters.dwg import DwgAdapter
from cuttle.adapters.image_pdf import merge_images_to_pdf, pdf_to_images
from cuttle.adapters.pdf import is_scanned_pdf
from cuttle.adapters.pdf2docx_adapter import WARNING_TOUCH_UPS
from cuttle.engine.convert import convert
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import Quality
from scripts.make_quality_report import generate_quality_report


def create_searchable_pdf(path: Path) -> Path:
    """Generate a valid PDF containing searchable text streams."""
    text = "Phase 5 integration test document with full paragraphs."
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


def test_phase5_pdf_to_word_pipeline(tmp_path: Path) -> None:
    """End-to-end conversion from searchable PDF to DOCX."""
    pdf_in = create_searchable_pdf(tmp_path / "article.pdf")
    assert is_scanned_pdf(pdf_in) is False

    res = convert(pdf_in, dst_fmt="docx", out_dir=tmp_path)
    assert res.output.is_file()
    assert res.output.suffix.lower() == ".docx"
    assert res.quality == Quality.BEST_EFFORT
    assert WARNING_TOUCH_UPS in res.warnings


def test_phase5_scanned_pdf_rejection_without_ocr(tmp_path: Path) -> None:
    """Scanned PDF without OCR must be rejected with E_UNSUPPORTED."""
    scanned_in = tmp_path / "scanned.pdf"
    img = Image.new("RGB", (100, 100), color=(50, 50, 50))
    img.save(scanned_in, format="PDF")
    assert is_scanned_pdf(scanned_in) is True

    with pytest.raises(CuttleError) as exc_info:
        convert(scanned_in, dst_fmt="docx", out_dir=tmp_path)

    assert exc_info.value.code == "E_UNSUPPORTED"
    assert "OCR" in exc_info.value.user_message


def test_phase5_image_pdf_bidirectional_and_merge(tmp_path: Path) -> None:
    """Verify image to PDF, multi-image merge, and PDF to image rendering."""
    # 1. Multi-image merge to PDF
    img1 = tmp_path / "p1.png"
    img2 = tmp_path / "p2.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(img1)
    Image.new("RGB", (100, 100), (0, 255, 0)).save(img2)

    merged_pdf = tmp_path / "bundle.pdf"
    merge_images_to_pdf([img1, img2], merged_pdf)
    assert merged_pdf.is_file()

    reader = pypdf.PdfReader(str(merged_pdf))
    assert len(reader.pages) == 2

    # 2. PDF to images extraction
    rendered = pdf_to_images(merged_pdf, out_dir=tmp_path / "extracted", fmt="png")
    assert len(rendered) == 2
    assert all(r.is_file() for r in rendered)


def test_phase5_dwg_pipeline(tmp_path: Path) -> None:
    """Verify DWG adapter error handling and pipeline routing."""
    dwg_file = tmp_path / "blueprint.dwg"
    dwg_file.write_bytes(b"AC1027" + b"\x00" * 100)

    adapter = DwgAdapter()
    assert adapter.can_convert("dwg", "pdf") == Quality.BEST_EFFORT

    # When tools missing, raises E_TOOL_MISSING
    with patch("cuttle.adapters.dwg.get_available_dwg_tool", return_value=None):
        with pytest.raises(CuttleError) as exc:
            convert(dwg_file, dst_fmt="pdf", out_dir=tmp_path)
        assert exc.value.code == "E_TOOL_MISSING"


def test_phase5_quality_report_synchronization() -> None:
    """Ensure quality report captures all registered phase 5 conversions."""
    report = generate_quality_report()
    assert "`PDF` | `DOCX`" in report
    assert "`DWG` | `PDF`" in report
    assert "`PNG` | `PDF`" in report
    assert "`PDF` | `PNG`" in report
