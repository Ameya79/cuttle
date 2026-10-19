"""Unit tests for Office document and PDF validation with font warning.

Per task cards P3-04 and P3-05:
- Validates docx, pptx, xlsx zip structures.
- Detects missing fonts between DOCX and PDF, raising warning:
  'Some fonts were replaced, layout may shift'
- Detects password-protected PDFs and unlocks with password.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pypdf
import pytest

from cuttle.adapters.pdf import (
    check_pdf_password,
    extract_docx_fonts,
    validate_pdf,
)
from cuttle.engine.errors import CuttleError
from cuttle.engine.validators import validate_office_document


def create_fake_docx(path: Path, fonts: list[str] | None = None) -> Path:
    """Create a minimal synthetic DOCX zip archive with fontTable.xml."""
    font_xml_items = ""
    if fonts:
        for f in fonts:
            font_xml_items += (
                '<w:font xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
                f' w:name="{f}"/>'
            )

    font_table_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:fonts xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">{font_xml_items}</w:fonts>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<document/>")
        if fonts:
            z.writestr("word/fontTable.xml", font_table_xml)

    path.write_bytes(buf.getvalue())
    return path


def create_simple_pdf(path: Path, password: str | None = None) -> Path:
    """Create a minimal synthetic PDF."""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if password:
        writer.encrypt(password)
    with open(path, "wb") as f:
        writer.write(f)
    return path


class TestOfficeDocumentValidators:
    def test_valid_docx(self, tmp_path: Path) -> None:
        p = create_fake_docx(tmp_path / "valid.docx")
        vr = validate_office_document(p)
        assert vr.ok

    def test_missing_required_xml_fails(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.docx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("other.xml", "data")
        vr = validate_office_document(p)
        assert not vr.ok
        assert "missing required component" in vr.reason

    def test_corrupt_zip_fails(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.xlsx"
        p.write_bytes(b"garbage not a zip")
        vr = validate_office_document(p)
        assert not vr.ok
        assert "Corrupt" in vr.reason


class TestPdfValidationAndFontWarning:
    def test_valid_pdf_no_docx_passes(self, tmp_path: Path) -> None:
        pdf_path = create_simple_pdf(tmp_path / "test.pdf")
        vr = validate_pdf(pdf_path)
        assert vr.ok
        assert len(vr.warnings) == 0

    def test_font_substitution_warning_triggered(self, tmp_path: Path) -> None:
        # Source DOCX requires a rare custom font
        docx_path = create_fake_docx(
            tmp_path / "fonts_missing.docx",
            fonts=["ObscureFantasyScriptPro"],
        )
        assert "ObscureFantasyScriptPro" in extract_docx_fonts(docx_path)

        # Output PDF has only standard/empty fonts
        pdf_path = create_simple_pdf(tmp_path / "output.pdf")

        vr = validate_pdf(pdf_path, src_docx=docx_path)
        assert vr.ok
        assert "Some fonts were replaced, layout may shift" in vr.warnings

    def test_font_matching_has_no_warning(self, tmp_path: Path) -> None:
        # When docx uses standard core fonts
        docx_path = create_fake_docx(tmp_path / "standard.docx", fonts=["Helvetica", "Times"])
        pdf_path = create_simple_pdf(tmp_path / "output.pdf")

        vr = validate_pdf(pdf_path, src_docx=docx_path)
        assert vr.ok
        assert len(vr.warnings) == 0


class TestPdfPasswordHandling:
    def test_unencrypted_pdf_succeeds(self, tmp_path: Path) -> None:
        pdf_path = create_simple_pdf(tmp_path / "open.pdf")
        reader = check_pdf_password(pdf_path)
        assert not reader.is_encrypted

    def test_encrypted_pdf_without_password_raises_e_src_password(self, tmp_path: Path) -> None:
        pdf_path = create_simple_pdf(tmp_path / "locked.pdf", password="secret123")
        with pytest.raises(CuttleError) as exc_info:
            check_pdf_password(pdf_path)
        assert exc_info.value.code == "E_SRC_PASSWORD"
        assert "password-protected" in exc_info.value.user_message

    def test_encrypted_pdf_with_wrong_password_raises_e_src_password(self, tmp_path: Path) -> None:
        pdf_path = create_simple_pdf(tmp_path / "locked.pdf", password="secret123")
        with pytest.raises(CuttleError) as exc_info:
            check_pdf_password(pdf_path, password="wrong_password")
        assert exc_info.value.code == "E_SRC_PASSWORD"

    def test_encrypted_pdf_with_correct_password_unlocks(self, tmp_path: Path) -> None:
        pdf_path = create_simple_pdf(tmp_path / "locked.pdf", password="secret123")
        reader = check_pdf_password(pdf_path, password="secret123")
        assert len(reader.pages) == 1
