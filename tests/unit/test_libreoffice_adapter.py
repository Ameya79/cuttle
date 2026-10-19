"""Unit tests for LibreOffice headless adapter.

Per task card P3-03:
- Headless argv structure
- Single concurrency locking
- Process tree kill on timeout or cancel
- Validation with pypdf (>= 1 page)
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cuttle.adapters.libreoffice import (
    _LIBREOFFICE_LOCK,
    LibreOfficeAdapter,
)
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality


class TestLibreOfficeArgvAndCapabilities:
    def test_can_convert(self) -> None:
        adapter = LibreOfficeAdapter(soffice_path="fake/soffice.exe")
        assert adapter.can_convert("docx", "pdf") == Quality.LOSSLESS
        assert adapter.can_convert("pptx", "pdf") == Quality.LOSSLESS
        assert adapter.can_convert("xlsx", "pdf") == Quality.LOSSLESS
        assert adapter.can_convert("odt", "pdf") == Quality.LOSSLESS
        assert adapter.can_convert("pdf", "docx") is None
        assert adapter.can_convert("mp4", "pdf") is None

    def test_build_argv(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter(soffice_path=tmp_path / "soffice.exe")
        src = tmp_path / "slides.pptx"
        profile_dir = tmp_path / "lo_profile"
        out_dir = tmp_path / "lo_out"

        argv = adapter.build_argv(src, profile_dir, out_dir)

        assert argv[0] == str(tmp_path / "soffice.exe")
        assert "--headless" in argv
        assert "--norestore" in argv
        assert "--nolockcheck" in argv
        assert any(arg.startswith("-env:UserInstallation=") for arg in argv)
        assert "--convert-to" in argv
        assert argv[argv.index("--convert-to") + 1] == "pdf"
        assert "--outdir" in argv
        assert argv[argv.index("--outdir") + 1] == str(out_dir.resolve())
        assert str(src.resolve()) in argv

    def test_missing_soffice_raises_e_tool_missing(self) -> None:
        adapter = LibreOfficeAdapter()
        with patch(
            "cuttle.adapters.libreoffice.detect_office",
            return_value=MagicMock(installed=False, path=None),
        ):
            with pytest.raises(CuttleError) as exc_info:
                _ = adapter.soffice
            assert exc_info.value.code == "E_TOOL_MISSING"


class TestLibreOfficeExecution:
    def test_concurrency_lock_enforced(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter(soffice_path=tmp_path / "soffice.exe")
        plan = adapter.plan(
            tmp_path / "doc.docx",
            "pdf",
            tmp_path / "doc.pdf.cuttle-part",
            {},
        )

        lock_held_simultaneously = False

        def fake_run_command(*args: object, **kwargs: object) -> None:
            nonlocal lock_held_simultaneously
            # Try to acquire lock non-blocking while another job is in run
            acquired = _LIBREOFFICE_LOCK.acquire(blocking=False)
            if acquired:
                lock_held_simultaneously = True
                _LIBREOFFICE_LOCK.release()
            # Simulate producing PDF in outdir
            argv = list(args[0]) if args and isinstance(args[0], (list, tuple)) else []
            if "--outdir" in argv:
                out_dir = Path(argv[argv.index("--outdir") + 1])
                out_pdf = out_dir / "doc.pdf"
                out_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

        # Create dummy source
        (tmp_path / "doc.docx").write_bytes(b"dummy")

        with patch("cuttle.adapters.libreoffice.run_command", side_effect=fake_run_command):
            # Run two threads
            t1 = threading.Thread(
                target=adapter.run,
                args=(plan, lambda pct, msg: None, CancelToken()),
            )
            t2 = threading.Thread(
                target=adapter.run,
                args=(plan, lambda pct, msg: None, CancelToken()),
            )
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert not lock_held_simultaneously

    def test_cancellation_before_execution(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter(soffice_path=tmp_path / "soffice.exe")
        token = CancelToken()
        token.cancel()

        plan = adapter.plan(
            tmp_path / "cancel.docx",
            "pdf",
            tmp_path / "cancel.pdf.cuttle-part",
            {},
        )

        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda pct, msg: None, token)
        assert exc_info.value.code == "E_CANCELLED"

    def test_hung_process_timeout_or_failure(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter(soffice_path=tmp_path / "soffice.exe")
        (tmp_path / "hung.docx").write_bytes(b"data")

        plan = adapter.plan(
            tmp_path / "hung.docx",
            "pdf",
            tmp_path / "hung.pdf.cuttle-part",
            {},
        )

        with patch(
            "cuttle.adapters.libreoffice.run_command",
            side_effect=CuttleError("E_TIMEOUT", "Command timed out"),
        ):
            with pytest.raises(CuttleError) as exc_info:
                adapter.run(plan, lambda pct, msg: None, CancelToken())
            assert exc_info.value.code == "E_TIMEOUT"


class TestLibreOfficeValidation:
    def test_validate_missing_file(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter()
        vr = adapter.validate(tmp_path / "src.docx", tmp_path / "missing.pdf")
        assert not vr.ok
        assert "does not exist" in vr.reason

    def test_validate_empty_file(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter()
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")
        vr = adapter.validate(tmp_path / "src.docx", empty_pdf)
        assert not vr.ok
        assert "empty" in vr.reason

    def test_validate_corrupt_pdf(self, tmp_path: Path) -> None:
        adapter = LibreOfficeAdapter()
        corrupt = tmp_path / "corrupt.pdf"
        corrupt.write_bytes(b"Not a real PDF payload")
        vr = adapter.validate(tmp_path / "src.docx", corrupt)
        assert not vr.ok
        assert "corrupt or invalid" in vr.reason.lower()

    def test_validate_valid_pdf_with_pages(self, tmp_path: Path) -> None:
        import pypdf

        valid_pdf = tmp_path / "valid.pdf"
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=72, height=72)
        with open(valid_pdf, "wb") as f:
            writer.write(f)

        adapter = LibreOfficeAdapter()
        vr = adapter.validate(tmp_path / "src.docx", valid_pdf)
        assert vr.ok
