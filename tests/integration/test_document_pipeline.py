"""Integration tests for Phase 3 document conversion pipeline.

Per TRD §6.5, Part 3, and Task card P3-09:
- End-to-end document conversions via Pandoc (md, html, docx, txt).
- Verified source immutability (SHA-256 hashes unchanged).
- Zero .cuttle-part temporary file leaks.
- Safe collision avoidance.
- Proper handling of locked PDFs and font substitution warnings.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cuttle.engine.convert import convert, list_targets
from cuttle.engine.errors import CuttleError


def sha256_of_file(path: Path) -> str:
    """Compute sha256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestDocumentPipeline:
    def test_list_targets_for_documents(self, fixtures_dir: Path) -> None:
        md_file = fixtures_dir / "doc.md"
        targets = list_targets(md_file)
        target_fmts = {t.fmt for t in targets}
        assert "docx" in target_fmts
        assert "html" in target_fmts
        assert "txt" in target_fmts

    def test_md_to_docx_end_to_end_pipeline(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "doc.md"
        orig_hash = sha256_of_file(src)

        res = convert(src, "docx", out_dir=tmp_path)
        assert res.output.is_file()
        assert res.output.suffix == ".docx"
        assert res.output.name == "doc (converted).docx"

        # Check source immutability
        assert sha256_of_file(src) == orig_hash

        # Verify no .cuttle-part left behind
        parts = list(tmp_path.glob("*.cuttle-part"))
        assert len(parts) == 0

    def test_md_to_html_end_to_end_pipeline(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "doc.md"
        orig_hash = sha256_of_file(src)

        res = convert(src, "html", out_dir=tmp_path)
        assert res.output.is_file()
        assert res.output.name == "doc (converted).html"
        assert "<html" in res.output.read_text(encoding="utf-8").lower()

        assert sha256_of_file(src) == orig_hash
        assert len(list(tmp_path.glob("*.cuttle-part"))) == 0

    def test_txt_to_md_end_to_end_pipeline(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "doc.txt"
        orig_hash = sha256_of_file(src)

        res = convert(src, "md", out_dir=tmp_path)
        assert res.output.is_file()
        assert res.output.name == "doc (converted).md"

        assert sha256_of_file(src) == orig_hash
        assert len(list(tmp_path.glob("*.cuttle-part"))) == 0

    def test_docx_to_md_end_to_end_pipeline(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "doc.docx"
        orig_hash = sha256_of_file(src)

        res = convert(src, "md", out_dir=tmp_path)
        assert res.output.is_file()
        assert res.output.name == "doc (converted).md"

        assert sha256_of_file(src) == orig_hash
        assert len(list(tmp_path.glob("*.cuttle-part"))) == 0

    def test_document_collision_naming(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "doc.md"

        res1 = convert(src, "docx", out_dir=tmp_path)
        assert res1.output.name == "doc (converted).docx"

        res2 = convert(src, "docx", out_dir=tmp_path)
        assert res2.output.name == "doc (converted) (2).docx"

        res3 = convert(src, "docx", out_dir=tmp_path)
        assert res3.output.name == "doc (converted) (3).docx"
        assert len(list(tmp_path.glob("*.cuttle-part"))) == 0

    def test_locked_pdf_fixture_detection(self, fixtures_dir: Path) -> None:
        from cuttle.adapters.pdf import check_pdf_password

        locked = fixtures_dir / "locked.pdf"
        assert locked.is_file()

        with pytest.raises(CuttleError) as exc_info:
            check_pdf_password(locked)
        assert exc_info.value.code == "E_SRC_PASSWORD"

        # Unlock with fixture password
        reader = check_pdf_password(locked, password="secret123")
        assert len(reader.pages) == 1
