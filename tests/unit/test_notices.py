"""Unit tests for third-party notices and GPL source offer generation (P6-04).

Per TRD task card P6-04:
- Generates THIRD_PARTY_NOTICES.md containing every bundled tool and library with version,
  license, and source link.
- Contains the mandatory GPL-3.0 source offer text.
"""

from __future__ import annotations

from pathlib import Path

from scripts.make_notices import (
    GPL_SOURCE_OFFER,
    THIRD_PARTY_COMPONENTS,
    generate_notices,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_gpl_source_offer_text() -> None:
    """GPL source offer must explicitly offer complete source code and point to repo."""
    assert "Written Offer for Source Code" in GPL_SOURCE_OFFER
    assert "GNU General Public License" in GPL_SOURCE_OFFER
    assert "https://github.com/Ameya79/cuttle" in GPL_SOURCE_OFFER


def test_third_party_components_completeness() -> None:
    """Component list must include core engines and major third-party libraries."""
    names = {comp["name"] for comp in THIRD_PARTY_COMPONENTS}
    required = {
        "FFmpeg",
        "Pandoc",
        "PySide6 (Qt for Python)",
        "pdf2docx",
        "PyMuPDF",
        "Pillow",
        "pillow-heif",
        "pypdf",
        "Typer",
        "psutil",
        "pywin32",
    }
    missing = required - names
    assert not missing, f"Missing required components in notices: {missing}"

    for comp in THIRD_PARTY_COMPONENTS:
        assert comp["version"]
        assert comp["license"]
        assert comp["source"].startswith("http")


def test_generate_notices_file_output(tmp_path: Path) -> None:
    """generate_notices() must produce valid Markdown with headers, table, and add-ons."""
    text = generate_notices()
    assert "# Third-Party Notices & Licenses" in text
    assert "## Written Offer for Source Code" in text
    assert "## Third-Party Components" in text
    assert "## Optional Add-On Integrations" in text
    assert "LibreOffice" in text
    assert "Tesseract-OCR" in text

    # Verify root file matches generator output
    notices_file = PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"
    assert notices_file.is_file()
    assert text.strip() == notices_file.read_text(encoding="utf-8").strip()
