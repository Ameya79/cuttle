"""Unit tests for Pandoc document conversion adapter.

Per task card P3-01:
- Argv builders with explicit -f and -t
- Appends --sandbox when supported
- Validates round trips (md -> docx -> md keeps headings)
- Handles empty/corrupt input cleanly
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cuttle.adapters.pandoc import (
    PANDOC_INPUT_FORMAT_MAP,
    PANDOC_OUTPUT_FORMAT_MAP,
    PandocAdapter,
    check_sandbox_supported,
)
from cuttle.engine.convert import convert
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality


class TestPandocArgvBuilder:
    def test_format_mappings_exist(self) -> None:
        for fmt in ("md", "html", "docx", "txt"):
            assert fmt in PANDOC_INPUT_FORMAT_MAP
            assert fmt in PANDOC_OUTPUT_FORMAT_MAP

    def test_can_convert(self) -> None:
        adapter = PandocAdapter(pandoc_path="pandoc.exe")
        assert adapter.can_convert("md", "docx") == Quality.LOSSLESS
        assert adapter.can_convert("md", "html") == Quality.LOSSLESS
        assert adapter.can_convert("md", "txt") == Quality.LOSSLESS
        assert adapter.can_convert("docx", "md") == Quality.LOSSY
        assert adapter.can_convert("docx", "txt") == Quality.LOSSY
        assert adapter.can_convert("md", "md") is None
        assert adapter.can_convert("mp4", "docx") is None

    def test_build_argv_explicit_f_and_t(self, tmp_path: Path) -> None:
        adapter = PandocAdapter(pandoc_path="pandoc.exe")
        src = tmp_path / "notes.md"
        src.write_text("# Hello World\n", encoding="utf-8")
        tmp_out = tmp_path / "out.docx.cuttle-part"

        with patch("cuttle.adapters.pandoc.check_sandbox_supported", return_value=True):
            argv = adapter.build_argv(src, "docx", tmp_out)

        assert argv[0] == "pandoc.exe"
        assert "-f" in argv
        assert argv[argv.index("-f") + 1] == "markdown"
        assert "-t" in argv
        assert argv[argv.index("-t") + 1] == "docx"
        assert "--sandbox" in argv
        assert "-o" in argv
        assert argv[argv.index("-o") + 1] == str(tmp_out)
        assert str(src) in argv

    def test_build_argv_html_adds_standalone(self, tmp_path: Path) -> None:
        adapter = PandocAdapter(pandoc_path="pandoc.exe")
        src = tmp_path / "doc.md"
        src.write_text("Text", encoding="utf-8")
        tmp_out = tmp_path / "out.html.cuttle-part"

        with patch("cuttle.adapters.pandoc.check_sandbox_supported", return_value=False):
            argv = adapter.build_argv(src, "html", tmp_out)

        assert "-s" in argv
        assert "--sandbox" not in argv

    def test_check_sandbox_supported(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Options:\n  --sandbox[=true|false]\n"
            check_sandbox_supported.cache_clear()
            assert check_sandbox_supported("dummy_pandoc") is True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Old Pandoc 1.0\n"
            check_sandbox_supported.cache_clear()
            assert check_sandbox_supported("dummy_pandoc") is False


class TestPandocIntegration:
    @pytest.fixture(autouse=True)
    def check_pandoc(self) -> None:
        adapter = PandocAdapter()
        try:
            _ = adapter.pandoc
        except CuttleError:
            pytest.skip("pandoc binary not installed")

    def test_md_to_docx_roundtrip_keeps_headings(self, tmp_path: Path) -> None:
        src_md = tmp_path / "report.md"
        heading_text = "# Executive Summary & Key Findings"
        para_text = "This is a detailed paragraph testing Pandoc document generation."
        subheading_text = "## Secondary Analysis"
        src_md.write_text(f"{heading_text}\n\n{para_text}\n\n{subheading_text}\n", encoding="utf-8")

        # 1. Convert MD -> DOCX
        res_docx = convert(src_md, "docx", out_dir=tmp_path)
        assert res_docx.output.is_file()
        assert res_docx.output.suffix == ".docx"
        assert zipfile.is_zipfile(res_docx.output)

        # 2. Convert DOCX -> MD (roundtrip)
        res_md = convert(res_docx.output, "md", out_dir=tmp_path)
        assert res_md.output.is_file()
        roundtrip_content = res_md.output.read_text(encoding="utf-8")

        assert "Executive Summary & Key Findings" in roundtrip_content
        assert "Secondary Analysis" in roundtrip_content

    def test_md_to_html_generates_valid_html(self, tmp_path: Path) -> None:
        src = tmp_path / "index.md"
        src.write_text("# Welcome to Cuttle\n\nFast offline converter.", encoding="utf-8")

        res = convert(src, "html", out_dir=tmp_path)
        assert res.output.is_file()
        content = res.output.read_text(encoding="utf-8")
        assert "<html" in content.lower()
        assert "Welcome to Cuttle" in content

    def test_empty_input_fails_cleanly(self, tmp_path: Path) -> None:
        src = tmp_path / "empty.md"
        src.write_text("", encoding="utf-8")

        with pytest.raises(CuttleError) as exc_info:
            convert(src, "docx", out_dir=tmp_path)
        assert exc_info.value.code == "E_SRC_CORRUPT"

    def test_cancellation(self, tmp_path: Path) -> None:
        adapter = PandocAdapter()
        src = tmp_path / "cancel.md"
        src.write_text("content", encoding="utf-8")
        token = CancelToken()
        token.cancel()

        plan = adapter.plan(src, "docx", tmp_path / "tmp.docx.cuttle-part", {})
        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda pct, msg: None, token)
        assert exc_info.value.code == "E_CANCELLED"
