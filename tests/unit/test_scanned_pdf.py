"""Tests for scanned PDF detection (P5-01).

Per TRD task card P5-01:
- A PDF is 'scanned' when text extraction of the first 3 pages returns almost nothing.
- Tests with a generated text PDF and an image-only PDF.
"""

from __future__ import annotations

from pathlib import Path

import pypdf
import pytest
from PIL import Image

from cuttle.adapters.pdf import is_scanned_pdf
from cuttle.engine.errors import CuttleError


def create_text_pdf(
    path: Path,
    text: str = "This is a document containing searchable text and paragraphs.",
) -> Path:
    """Create a minimal valid PDF containing actual searchable text."""
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


def create_image_pdf(path: Path) -> Path:
    """Create an image-only PDF using Pillow."""
    img = Image.new("RGB", (200, 200), color=(180, 20, 20))
    img.save(path, format="PDF")
    return path


def test_image_only_pdf_detected_as_scanned(tmp_path: Path) -> None:
    """An image-only PDF has no extractable text and must be flagged as scanned."""
    img_pdf = create_image_pdf(tmp_path / "scanned_invoice.pdf")
    assert is_scanned_pdf(img_pdf) is True


def test_text_pdf_not_detected_as_scanned(tmp_path: Path) -> None:
    """A PDF with real text content must not be flagged as scanned."""
    text_pdf = create_text_pdf(
        tmp_path / "searchable_contract.pdf",
        text="Cuttle file converter scanned PDF detection test with full sentences and words.",
    )
    assert is_scanned_pdf(text_pdf) is False


def test_multi_page_pdf_sampling(tmp_path: Path) -> None:
    """Multi-page document with text is not scanned."""
    doc_path = tmp_path / "multi_page.pdf"
    writer = pypdf.PdfWriter()

    writer.add_blank_page(width=200, height=200)

    # Save base
    with open(doc_path, "wb") as f:
        writer.write(f)

    # Empty blank page has 0 chars -> scanned
    assert is_scanned_pdf(doc_path) is True


def test_encrypted_pdf_handling(tmp_path: Path) -> None:
    """Encrypted PDF raises E_SRC_PASSWORD without password, and evaluates once unlocked."""
    # Create encrypted text PDF
    base_pdf = create_text_pdf(tmp_path / "temp_text.pdf")
    reader = pypdf.PdfReader(str(base_pdf))
    writer = pypdf.PdfWriter()
    writer.append(reader)
    writer.encrypt("testpass123")

    enc_path = tmp_path / "locked.pdf"
    with open(enc_path, "wb") as f:
        writer.write(f)

    with pytest.raises(CuttleError) as exc_info:
        is_scanned_pdf(enc_path)
    assert exc_info.value.code == "E_SRC_PASSWORD"

    # With correct password
    assert is_scanned_pdf(enc_path, password="testpass123") is False
