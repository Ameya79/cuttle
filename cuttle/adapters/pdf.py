"""PDF validation and font substitution analysis.

Per TRD task cards P3-04 and P3-05:
- Validates PDF documents open cleanly via pypdf and contain >= 1 page.
- Detects encryption and password requirements (E_SRC_PASSWORD).
- Compares DOCX source fonts with PDF fonts to issue warnings:
  'Some fonts were replaced, layout may shift'
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pypdf

from cuttle.engine.errors import CuttleError
from cuttle.engine.types import ValidationResult


def extract_docx_fonts(docx_path: Path) -> set[str]:
    """Extract font names declared in a DOCX fontTable.xml."""
    fonts: set[str] = set()
    try:
        with zipfile.ZipFile(docx_path, "r") as z:
            if "word/fontTable.xml" in z.namelist():
                xml_data = z.read("word/fontTable.xml")
                root = ET.fromstring(xml_data)
                # Find all w:font elements
                for elem in root.iter():
                    if elem.tag.endswith("font"):
                        name = elem.attrib.get(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}name"
                        )
                        if name:
                            fonts.add(name.strip())
    except Exception:
        pass
    return fonts


def extract_pdf_fonts(pdf_reader: pypdf.PdfReader) -> set[str]:
    """Extract font names referenced across all pages in a PDF document."""
    pdf_fonts: set[str] = set()
    try:
        for page in pdf_reader.pages:
            resources = page.get("/Resources")
            if not resources or not isinstance(resources, dict):
                continue
            font_dict = resources.get("/Font")
            if not font_dict or not isinstance(font_dict, dict):
                continue

            for _, font_obj in font_dict.items():
                resolved = font_obj.get_object() if hasattr(font_obj, "get_object") else font_obj
                if isinstance(resolved, dict):
                    base_font = str(resolved.get("/BaseFont", ""))
                    # Strip leading slash and subset tag (e.g. /ABCDEF+Calibri -> Calibri)
                    clean_name = base_font.lstrip("/")
                    if "+" in clean_name:
                        clean_name = clean_name.split("+", 1)[1]
                    # Also strip hyphen variations (e.g. TimesNewRomanPS-BoldMT)
                    clean_name = re.sub(r"[-,].*$", "", clean_name)
                    if clean_name:
                        pdf_fonts.add(clean_name.lower())
    except Exception:
        pass
    return pdf_fonts


def check_pdf_password(pdf_path: Path, password: str | None = None) -> pypdf.PdfReader:
    """Inspect PDF encryption status and decrypt if password is provided.

    Raises:
        CuttleError("E_SRC_PASSWORD"): If file is encrypted and no password or
            incorrect password provided.
    """
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as exc:
        raise CuttleError(
            code="E_SRC_CORRUPT",
            user_message=f"The PDF file '{pdf_path.name}' is corrupt or invalid.",
            detail=str(exc),
        ) from exc

    if reader.is_encrypted:
        if not password:
            raise CuttleError(
                code="E_SRC_PASSWORD",
                user_message=f"The file '{pdf_path.name}' is password-protected.",
                detail="PDF is encrypted and requires a password to open.",
            )
        try:
            result = reader.decrypt(password)
            if result == 0:
                raise CuttleError(
                    code="E_SRC_PASSWORD",
                    user_message="Incorrect password for protected PDF.",
                    detail="pypdf decrypt returned 0 (failed).",
                )
        except Exception as exc:
            if isinstance(exc, CuttleError):
                raise
            raise CuttleError(
                code="E_SRC_PASSWORD",
                user_message="Could not unlock PDF with the provided password.",
                detail=str(exc),
            ) from exc

    return reader


def validate_pdf(
    pdf_path: Path,
    src_docx: Path | None = None,
    password: str | None = None,
) -> ValidationResult:
    """Validate PDF integrity and inspect for font substitutions."""
    if not pdf_path.is_file():
        return ValidationResult(ok=False, reason="Output PDF does not exist.")

    try:
        if pdf_path.stat().st_size == 0:
            return ValidationResult(ok=False, reason="Output PDF is empty (0 bytes).")
    except OSError as exc:
        return ValidationResult(ok=False, reason=f"Could not read output PDF: {exc}")

    try:
        reader = check_pdf_password(pdf_path, password=password)
    except CuttleError as err:
        return ValidationResult(ok=False, reason=err.user_message)

    if len(reader.pages) < 1:
        return ValidationResult(ok=False, reason="PDF contains zero pages.")

    warnings: list[str] = []

    # Check font substitution between docx and pdf
    if src_docx and src_docx.is_file() and src_docx.suffix.lower() == ".docx":
        docx_fonts = extract_docx_fonts(src_docx)
        if docx_fonts:
            pdf_fonts = extract_pdf_fonts(reader)
            # Standard universal core fonts that are always safe
            core_substitutes = {"times", "helvetica", "courier", "symbol", "zapfdingbats"}
            # Check if any docx font was substituted
            missing_fonts = [
                f
                for f in docx_fonts
                if f.lower() not in pdf_fonts
                and not any(f.lower() in pf or pf in f.lower() for pf in pdf_fonts)
                and f.lower() not in core_substitutes
            ]
            if missing_fonts:
                warnings.append("Some fonts were replaced, layout may shift")

    return ValidationResult(ok=True, warnings=warnings)


def is_scanned_pdf(
    pdf_path: Path,
    password: str | None = None,
    max_pages: int = 3,
    min_chars: int = 30,
) -> bool:
    """Detect if a PDF is primarily scanned / image-based rather than text.

    Per TRD P5-01:
    A PDF is considered 'scanned' when text extraction across the first
    `max_pages` pages (default 3) returns almost nothing (< `min_chars`).

    Args:
        pdf_path: Path to the PDF file.
        password: Optional decryption password.
        max_pages: Maximum number of leading pages to sample (default: 3).
        min_chars: Character count threshold below which the document is
            classified as scanned (default: 30 non-whitespace characters).

    Returns:
        True if the PDF is scanned / contains minimal text, False otherwise.
    """
    reader = check_pdf_password(pdf_path, password=password)
    sample_pages = reader.pages[:max_pages]
    if not sample_pages:
        return True

    total_chars = 0
    for page in sample_pages:
        try:
            text = page.extract_text() or ""
            # Strip all whitespace characters to count actual textual glyphs
            cleaned = "".join(text.split())
            total_chars += len(cleaned)
        except Exception:
            continue

    return total_chars < min_chars
