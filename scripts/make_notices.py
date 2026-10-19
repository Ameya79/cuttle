"""Generate third-party open-source notices and GPL source offer (P6-04).

Per TRD task card P6-04:
- Generates THIRD_PARTY_NOTICES.md.
- Contains every bundled tool and library with version, license, and source link.
- Includes mandatory GPL-3.0 source offer text.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"

GPL_SOURCE_OFFER = """## Written Offer for Source Code

In accordance with the GNU General Public License version 3 (GPL-3.0), Cuttle Contributors
hereby offer to provide anyone with a complete machine-readable copy of the corresponding
source code for any binaries distributed with Cuttle, on a medium customarily used for
software interchange, for no charge other than the cost of physically performing source
distribution.

Source repository: https://github.com/Ameya79/cuttle
To request source archives or build instructions, open an issue or contact:
https://github.com/Ameya79/cuttle/issues
"""

THIRD_PARTY_COMPONENTS: list[dict[str, str]] = [
    {
        "name": "FFmpeg",
        "category": "External Binary Tool",
        "version": "n8.1.3",
        "license": "GPL-3.0 / LGPL-2.1+",
        "source": "https://ffmpeg.org/",
        "notes": "Multimedia demuxing, decoding, encoding, and filtering.",
    },
    {
        "name": "Pandoc",
        "category": "External Binary Tool",
        "version": "3.6.3",
        "license": "GPL-2.0+",
        "source": "https://github.com/jgm/pandoc",
        "notes": "Universal markup document parser and converter.",
    },
    {
        "name": "PySide6 (Qt for Python)",
        "category": "Python Library",
        "version": "6.8.0+",
        "license": "LGPL-3.0",
        "source": "https://code.qt.io/cgit/pyside/pyside-setup.git/",
        "notes": "Progress bar windows, tray icon, and desktop dialogs.",
    },
    {
        "name": "pdf2docx",
        "category": "Python Library",
        "version": "0.5.13+",
        "license": "GPL-3.0",
        "source": "https://github.com/dothinking/pdf2docx",
        "notes": "PDF layout reconstruction to Word DOCX format.",
    },
    {
        "name": "PyMuPDF",
        "category": "Python Library",
        "version": "2.0.0+",
        "license": "AGPL-3.0+",
        "source": "https://github.com/pymupdf/PyMuPDF",
        "notes": "High-performance vector and raster PDF page rendering.",
    },
    {
        "name": "Pillow",
        "category": "Python Library",
        "version": "10.0+",
        "license": "HPND",
        "source": "https://github.com/python-pillow/Pillow",
        "notes": "Bitmap image manipulation, alpha composition, and EXIF orientation.",
    },
    {
        "name": "pillow-heif",
        "category": "Python Library",
        "version": "0.13+",
        "license": "LGPL-3.0+",
        "source": "https://github.com/bigcat88/pillow_heif",
        "notes": "HEIF / HEIC codec plugin for Pillow.",
    },
    {
        "name": "pypdf",
        "category": "Python Library",
        "version": "4.0+",
        "license": "BSD-3-Clause",
        "source": "https://github.com/py-pdf/pypdf",
        "notes": "Pure-Python PDF inspection, encryption checking, and page manipulation.",
    },
    {
        "name": "Typer",
        "category": "Python Library",
        "version": "0.9+",
        "license": "MIT",
        "source": "https://github.com/tiangolo/typer",
        "notes": "Command-line interface builder for cuttle CLI.",
    },
    {
        "name": "psutil",
        "category": "Python Library",
        "version": "5.9+",
        "license": "BSD-3-Clause",
        "source": "https://github.com/giampaolo/psutil",
        "notes": "Cross-platform process and system monitoring utilities.",
    },
    {
        "name": "pywin32",
        "category": "Python Library",
        "version": "306+",
        "license": "PSF-2.0",
        "source": "https://github.com/mhammond/pywin32",
        "notes": "Windows API bindings for Job Objects, Named Pipes, and Registry.",
    },
    {
        "name": "windows-toasts",
        "category": "Python Library",
        "version": "1.1.0+",
        "license": "MIT",
        "source": "https://github.com/DatGuy/Windows-Toasts",
        "notes": "Native Windows 10/11 Toast notifications.",
    },
    {
        "name": "filetype",
        "category": "Python Library",
        "version": "1.2+",
        "license": "MIT",
        "source": "https://github.com/h2non/filetype.py",
        "notes": "File magic number signature probing.",
    },
]


def generate_notices() -> str:
    """Generate Markdown text for third-party notices and licensing disclosures."""
    lines: list[str] = [
        "# Third-Party Notices & Licenses",
        "",
        "Cuttle is distributed under the GNU General Public License version 3 (GPL-3.0).",
        "This project bundles, links, or interacts with the third-party open-source libraries",
        "and tools listed below.",
        "",
        GPL_SOURCE_OFFER,
        "## Third-Party Components",
        "",
        "| Component | Category | Version | License | Source / Repository | Notes |",
        "|:----------|:---------|:--------|:--------|:--------------------|:------|",
    ]

    for item in THIRD_PARTY_COMPONENTS:
        row = (
            f"| **{item['name']}** | {item['category']} | {item['version']} | "
            f"`{item['license']}` | [{item['name']} Source]({item['source']}) | {item['notes']} |"
        )
        lines.append(row)

    lines.extend(
        [
            "",
            "## Optional Add-On Integrations",
            "",
            "Cuttle can optionally detect and interact with the following standalone external",
            "tools if installed on the user's system (these tools are never bundled with Cuttle):",
            "",
            "- **LibreOffice** (MPL-2.0) — https://www.libreoffice.org/",
            "- **Tesseract-OCR** (Apache-2.0) — https://github.com/tesseract-ocr/tesseract",
            "- **LibreDWG** (GPL-3.0+) — https://www.gnu.org/software/libredwg/",
            "- **ODA File Converter** (Freeware) — https://www.opendesign.com/",
            "",
            "---",
            "*Notices automatically generated by `scripts/make_notices.py`.*",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Generate and write THIRD_PARTY_NOTICES.md."""
    content = generate_notices()
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"Third-party notices generated successfully at: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
