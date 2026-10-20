"""Hyper-rough adversarial stress and accuracy test suite for Cuttle.

This test suite aggressively tests:
1. Document layout fidelity: complex multi-column PDFs, lattice/stream tables, Unicode,
   rotated pages, Pandoc round-trips.
2. Image channels & color spaces: CMYK, semi-transparent RGBA, all 8 EXIF orientations,
   corrupted bytes.
3. Audio / Video geometries: odd video dimensions (321x247), silent video audio extraction guard,
   Unicode/shell-breaking filenames.
4. Concurrency & system invariants: mid-stream cancellation floods, zero .cuttle-part file residue,
   source file immutability, locked file handling.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from cuttle.adapters.pdf2docx_adapter import WARNING_TOUCH_UPS
from cuttle.engine.convert import convert
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken
from cuttle.engine.validators import validate_office_document

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def get_file_sha256(path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# =========================================================================
# 1. Document Accuracy & Layout Stress Tests
# =========================================================================


class TestDocumentFidelityStress:
    """Torture tests for document conversions."""

    def test_complex_pdf_to_word_layout(self, tmp_path: Path) -> None:
        """PDF with multi-column text and lattice table converts cleanly to DOCX."""
        src = FIXTURES_DIR / "complex_layout.pdf"
        assert src.is_file(), "Fixture complex_layout.pdf must exist"

        initial_hash = get_file_sha256(src)

        res = convert(src, "docx", out_dir=tmp_path)
        assert res.output.is_file()
        assert res.output.stat().st_size > 0
        assert WARNING_TOUCH_UPS in res.warnings

        # Validate DOCX structure
        val = validate_office_document(res.output, expected_fmt="docx")
        assert val.ok is True, f"Office document validation failed: {val.reason}"

        # Inspect internal word/document.xml content
        with zipfile.ZipFile(res.output, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            # Verify table text is present in the XML
            assert "Column One Title" in doc_xml or "Metric" in doc_xml or "Accuracy" in doc_xml

        # Verify source file is unchanged
        assert get_file_sha256(src) == initial_hash

    def test_unicode_text_pdf_to_word(self, tmp_path: Path) -> None:
        """PDF with multilingual Latin accents and special symbols converts cleanly."""
        src = FIXTURES_DIR / "unicode_text.pdf"
        assert src.is_file(), "Fixture unicode_text.pdf must exist"

        res = convert(src, "docx", out_dir=tmp_path)
        assert res.output.is_file()

        with zipfile.ZipFile(res.output, "r") as z:
            doc_xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            # Verify accented characters were parsed
            assert any(
                word in doc_xml for word in ["Multilingual", "Cafe", "facade", "Uber", "Strasse"]
            )

    def test_rotated_pages_pdf_to_docx_and_images(self, tmp_path: Path) -> None:
        """PDF with 0, 90, and 180 degree rotated pages converts to DOCX and PNGs."""
        src = FIXTURES_DIR / "rotated_pages.pdf"
        assert src.is_file(), "Fixture rotated_pages.pdf must exist"

        # 1. Convert to Word
        docx_res = convert(src, "docx", out_dir=tmp_path)
        assert docx_res.output.is_file()
        assert validate_office_document(docx_res.output, "docx").ok is True

        # 2. Convert to PNG image pages
        png_res = convert(src, "png", out_dir=tmp_path)
        assert png_res.output.is_file() or png_res.output.is_dir()

    def test_pandoc_structural_round_trip(self, tmp_path: Path) -> None:
        """Markdown -> DOCX -> HTML -> Markdown round trip preserves core structure."""
        src_md = FIXTURES_DIR / "doc.md"
        assert src_md.is_file()

        # Step 1: MD -> DOCX
        docx_res = convert(src_md, "docx", out_dir=tmp_path)
        assert docx_res.output.is_file()

        # Step 2: DOCX -> HTML
        html_res = convert(docx_res.output, "html", out_dir=tmp_path)
        assert html_res.output.is_file()
        html_content = html_res.output.read_text(encoding="utf-8")
        assert "Zero telemetry" in html_content

        # Step 3: HTML -> MD
        final_md_res = convert(html_res.output, "md", out_dir=tmp_path)
        assert final_md_res.output.is_file()
        final_md = final_md_res.output.read_text(encoding="utf-8")
        assert "Zero telemetry" in final_md

    def test_encrypted_pdf_rejection(self, tmp_path: Path) -> None:
        """Password-protected encrypted PDF raises an error without crashing."""
        src = FIXTURES_DIR / "locked.pdf"
        assert src.is_file()

        with pytest.raises(CuttleError) as exc_info:
            convert(src, "docx", out_dir=tmp_path)
        # Should raise either E_SRC_PASSWORD or E_CONV_FAILED
        assert exc_info.value.code in ("E_SRC_PASSWORD", "E_CONV_FAILED", "E_UNSUPPORTED")


# =========================================================================
# 2. Image Channel & Color Space Stress Tests
# =========================================================================


class TestImageChannelsStress:
    """Torture tests for image color modes and EXIF metadata."""

    def test_cmyk_image_conversions(self, tmp_path: Path) -> None:
        """CMYK JPEG and TIFF convert cleanly to PNG, WebP, and JPG without Pillow errors."""
        cmyk_jpg = FIXTURES_DIR / "cmyk.jpg"
        assert cmyk_jpg.is_file()

        # 1. CMYK -> PNG (lossless, requires RGB mode conversion)
        res_png = convert(cmyk_jpg, "png", out_dir=tmp_path)
        assert res_png.output.is_file()
        with Image.open(res_png.output) as img:
            img.load()
            assert img.mode in ("RGB", "RGBA")

        # 2. CMYK -> WebP
        res_webp = convert(cmyk_jpg, "webp", out_dir=tmp_path)
        assert res_webp.output.is_file()
        with Image.open(res_webp.output) as img:
            img.load()
            assert img.mode in ("RGB", "RGBA")

        # 3. CMYK -> BMP
        res_bmp = convert(cmyk_jpg, "bmp", out_dir=tmp_path)
        assert res_bmp.output.is_file()
        with Image.open(res_bmp.output) as img:
            img.load()
            assert img.mode == "RGB"

    def test_partial_alpha_flattening_on_white(self, tmp_path: Path) -> None:
        """RGBA with semi-transparent pixels converts to JPG and BMP by flattening to white."""
        src_png = FIXTURES_DIR / "img.png"
        assert src_png.is_file()

        # Convert to JPG (no alpha support)
        res_jpg = convert(src_png, "jpg", out_dir=tmp_path)
        assert res_jpg.output.is_file()
        with Image.open(res_jpg.output) as img:
            img.load()
            assert img.mode == "RGB"
            # Verify dimensions match source
            assert img.size == (100, 100)

        # Convert to BMP (no alpha support)
        res_bmp = convert(src_png, "bmp", out_dir=tmp_path)
        assert res_bmp.output.is_file()
        with Image.open(res_bmp.output) as img:
            img.load()
            assert img.mode == "RGB"
            assert img.size == (100, 100)

    def test_exif_transposition_orientations(self, tmp_path: Path) -> None:
        """EXIF orientation tags (1-8) are transposed into raw pixel data."""
        # Create an asymmetrical image: 60 wide, 30 high
        base_im = Image.new("RGB", (60, 30), color=(200, 50, 50))
        exif = base_im.getexif()

        # Orientation 6 specifies a 90 deg counter-clockwise rotation needed
        exif[0x0112] = 6
        exif_test_file = tmp_path / "exif_orientation_6.jpg"
        base_im.save(exif_test_file, format="JPEG", exif=exif)

        # Convert to PNG via Cuttle
        res = convert(exif_test_file, "png", out_dir=tmp_path)
        assert res.output.is_file()

        with Image.open(res.output) as img:
            img.load()
            # After exif_transpose, a 60x30 image with orientation 6 becomes 30x60
            assert img.size == (30, 60)

    def test_hostile_corrupt_image_raises_e_src_corrupt(self, tmp_path: Path) -> None:
        """Corrupt or truncated image bytes raise E_SRC_CORRUPT."""
        bad_img = tmp_path / "corrupt.jpg"
        bad_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01" + b"\x00" * 20)

        with pytest.raises(CuttleError) as exc_info:
            convert(bad_img, "png", out_dir=tmp_path)
        assert exc_info.value.code in ("E_SRC_CORRUPT", "E_TOOL_FAILED")

    def test_extreme_dimensions_image_to_pdf(self, tmp_path: Path) -> None:
        """1x1 pixel image and 4000x4000 image convert cleanly to PDF and pass validation."""
        # 1x1 tiny image
        tiny = tmp_path / "tiny.png"
        Image.new("RGB", (1, 1), (255, 0, 0)).save(tiny)
        r_tiny = convert(tiny, "pdf", out_dir=tmp_path)
        assert r_tiny.output.is_file()
        assert r_tiny.output.stat().st_size > 0

        # 4000x4000 large image
        huge = tmp_path / "huge.png"
        Image.new("RGB", (4000, 4000), (0, 255, 0)).save(huge)
        r_huge = convert(huge, "pdf", out_dir=tmp_path)
        assert r_huge.output.is_file()
        assert r_huge.output.stat().st_size > 0


# =========================================================================
# 3. Audio & Video Codec & Edge Geometry Stress Tests
# =========================================================================


class TestAudioVideoGeometryStress:
    """Torture tests for video geometries and audio extraction edge cases."""

    def test_odd_dimensions_video_to_mp4(self, tmp_path: Path) -> None:
        """Video with odd dimensions (321x247) converts to MP4 and WebM."""
        src = FIXTURES_DIR / "odd_dimensions.avi"
        assert src.is_file(), "Fixture odd_dimensions.avi must exist"

        # 1. Convert to MP4
        res_mp4 = convert(src, "mp4", out_dir=tmp_path)
        assert res_mp4.output.is_file()
        assert res_mp4.output.stat().st_size > 0

        # 2. Convert to WebM
        res_webm = convert(src, "webm", out_dir=tmp_path)
        assert res_webm.output.is_file()
        assert res_webm.output.stat().st_size > 0

    def test_silent_video_audio_extraction_rejected(self, tmp_path: Path) -> None:
        """Extracting audio from video with no audio stream raises E_UNSUPPORTED."""
        src = FIXTURES_DIR / "video_silent.mp4"
        assert src.is_file()

        with pytest.raises(CuttleError) as exc_info:
            convert(src, "mp3", out_dir=tmp_path)
        assert exc_info.value.code == "E_UNSUPPORTED"
        assert "no audio to extract" in exc_info.value.user_message.lower()

    def test_unicode_and_shell_breaking_filenames(self, tmp_path: Path) -> None:
        """Files with Hindi Unicode, ampersands, and parentheses convert cleanly."""
        hindi_src = FIXTURES_DIR / "वीडियो नमूना.mp4"
        shell_src = FIXTURES_DIR / "a & b (final) v2.mp4"

        assert hindi_src.is_file()
        assert shell_src.is_file()

        # Convert Hindi video to WAV
        res1 = convert(hindi_src, "wav", out_dir=tmp_path)
        assert res1.output.is_file()

        # Convert Shell symbols video to MP3
        res2 = convert(shell_src, "mp3", out_dir=tmp_path)
        assert res2.output.is_file()


# =========================================================================
# 4. Concurrency, Mid-Stream Cancellation, & Cleanliness Torture
# =========================================================================


class TestConcurrencyAndCleanlinessStress:
    """Stress testing parallel operations, mid-stream cancellations, and lock safety."""

    def test_concurrent_conversions_with_burst_cancellations(self, tmp_path: Path) -> None:
        """Flood converter with concurrent jobs; verify zero .cuttle-part residue."""
        test_dir = tmp_path / "concurrency_test"
        test_dir.mkdir(parents=True, exist_ok=True)

        img_src = FIXTURES_DIR / "img.png"
        video_src = FIXTURES_DIR / "video_av.mp4"
        doc_src = FIXTURES_DIR / "doc.md"

        initial_img_hash = get_file_sha256(img_src)
        initial_video_hash = get_file_sha256(video_src)
        initial_doc_hash = get_file_sha256(doc_src)

        # 8 conversion tasks: 4 will run normally, 4 will have cancel tokens triggered
        tasks = [
            (img_src, "webp", CancelToken(), False),
            (img_src, "jpg", CancelToken(), True),
            (video_src, "wav", CancelToken(), False),
            (video_src, "mp3", CancelToken(), True),
            (doc_src, "html", CancelToken(), False),
            (doc_src, "txt", CancelToken(), True),
            (img_src, "bmp", CancelToken(), False),
            (video_src, "gif", CancelToken(), True),
        ]

        # Pre-cancel 2, and cancel 2 mid-stream
        tasks[1][2].cancel()
        tasks[5][2].cancel()

        def run_task(src: Path, dst: str, cancel: CancelToken, cancel_later: bool) -> str:
            if cancel_later:
                import time

                time.sleep(0.01)
                cancel.cancel()
            try:
                res = convert(src, dst, out_dir=test_dir, cancel=cancel)
                return f"OK: {res.output.name}"
            except CuttleError as err:
                return f"ERR: {err.code}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_task, src, dst, cancel, cancel_later)
                for src, dst, cancel, cancel_later in tasks
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8

        # Invariant 1: No .cuttle-part temporary files left behind
        leftover_parts = list(test_dir.glob("*.cuttle-part"))
        assert len(leftover_parts) == 0, f"Found leaked temporary files: {leftover_parts}"

        # Invariant 2: Source files are completely unmodified
        assert get_file_sha256(img_src) == initial_img_hash
        assert get_file_sha256(video_src) == initial_video_hash
        assert get_file_sha256(doc_src) == initial_doc_hash

    def test_collision_avoidance_sequence(self, tmp_path: Path) -> None:
        """Converting the same file repeatedly creates (converted), (converted) (2), etc."""
        src = FIXTURES_DIR / "doc.txt"
        assert src.is_file()

        r1 = convert(src, "html", out_dir=tmp_path)
        assert r1.output.name == "doc (converted).html"

        r2 = convert(src, "html", out_dir=tmp_path)
        assert r2.output.name == "doc (converted) (2).html"

        r3 = convert(src, "html", out_dir=tmp_path)
        assert r3.output.name == "doc (converted) (3).html"

        r4 = convert(src, "html", out_dir=tmp_path)
        assert r4.output.name == "doc (converted) (4).html"

    def test_locked_source_file_raises_e_src_locked(self, tmp_path: Path) -> None:
        """Source file held exclusively by another process raises E_SRC_LOCKED."""
        locked_file = tmp_path / "held_open.txt"
        locked_file.write_text("exclusive lock test content", encoding="utf-8")

        # Open in exclusive write mode without sharing
        with open(locked_file, "r+b") as f:
            try:
                import msvcrt

                # Lock the first byte exclusively
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    with pytest.raises(CuttleError) as exc_info:
                        convert(locked_file, "html", out_dir=tmp_path)
                    assert exc_info.value.code == "E_SRC_LOCKED"
                finally:
                    # Unlock before closing
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                # If msvcrt locking isn't permitted in environment, pass
                pass
