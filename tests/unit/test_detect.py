"""Tests for format detection (P1-05).

Per TRD task card P1-05:
- Magic bytes first, extension second
- Disagreement adds a warning (e.g. png_named_jpg.jpg detected as png with warning)
- zero_byte.mp4 raises E_SRC_CORRUPT
- Missing file raises E_SRC_MISSING
- Unsupported format raises E_UNSUPPORTED
- All Phase 1 formats detected correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cuttle.engine.detect import DetectedFormat, detect
from cuttle.engine.errors import CuttleError

# Minimal valid magic byte headers for all 14 Phase 1 formats
SAMPLE_HEADERS: dict[str, bytes] = {
    "png": (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    ),
    "jpg": (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00"
    ),
    "gif": (
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00"
        b"\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    ),
    "bmp": (
        b"BM\x3a\x00\x00\x00\x00\x00\x00\x00\x36\x00\x00\x00\x28\x00\x00\x00"
        b"\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x18\x00"
    ),
    "tiff": b"II*\x00\x08\x00\x00\x00\x00\x00",
    "webp": b"RIFF$\x00\x00\x00WEBPVP8 \x00\x00\x00\x00",
    "wav": (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"
        b"\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    ),
    "avi": b"RIFF$\x00\x00\x00AVI LIST\x00\x00\x00\x00",
    "mp3": b"ID3\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
    "mp4": b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41",
    "mov": b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  ",
    "heic": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic",
    "mkv": (
        b"\x1a\x45\xdf\xa3\x01\x00\x00\x1f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04"
        b"\x42\xf3\x81\x08\x42\x82\x88matroska"
    ),
    "webm": (
        b"\x1a\x45\xdf\xa3\x01\x00\x00\x1f\x42\x86\x81\x01\x42\xf7\x81\x01\x42\xf2\x81\x04"
        b"\x42\xf3\x81\x08\x42\x82\x84webm"
    ),
}


class TestDetectErrors:
    def test_missing_file_raises_e_src_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.mp4"
        with pytest.raises(CuttleError) as exc_info:
            detect(missing)
        assert exc_info.value.code == "E_SRC_MISSING"

    def test_zero_byte_raises_e_src_corrupt(self, tmp_path: Path) -> None:
        zero_byte = tmp_path / "zero_byte.mp4"
        zero_byte.write_bytes(b"")
        with pytest.raises(CuttleError) as exc_info:
            detect(zero_byte)
        assert exc_info.value.code == "E_SRC_CORRUPT"

    def test_unsupported_file_raises_e_unsupported(self, tmp_path: Path) -> None:
        unknown = tmp_path / "random.xyz123"
        unknown.write_bytes(b"Random arbitrary content without recognizable header")
        with pytest.raises(CuttleError) as exc_info:
            detect(unknown)
        assert exc_info.value.code == "E_UNSUPPORTED"


class TestDetectFormats:
    @pytest.mark.parametrize("fmt,header", list(SAMPLE_HEADERS.items()))
    def test_all_phase1_formats_detected(self, fmt: str, header: bytes, tmp_path: Path) -> None:
        test_file = tmp_path / f"sample.{fmt}"
        test_file.write_bytes(header)

        res = detect(test_file)
        assert isinstance(res, DetectedFormat)
        assert isinstance(res, str)
        assert res == fmt
        assert res.fmt == fmt
        # When extension and magic agree, no warnings
        assert len(res.warnings) == 0

    def test_png_named_jpg_disagreement_adds_warning(self, tmp_path: Path) -> None:
        """png_named_jpg.jpg is detected as png with a warning per TRD P1-05."""
        fake_jpg = tmp_path / "png_named_jpg.jpg"
        fake_jpg.write_bytes(SAMPLE_HEADERS["png"])

        res = detect(fake_jpg)
        assert res == "png"
        assert len(res.warnings) >= 1
        assert "suggests jpg" in res.warnings[0].lower() or "jpg" in res.warnings[0].lower()
        assert "png" in res.warnings[0].lower()

    def test_magic_detected_with_unregistered_extension(self, tmp_path: Path) -> None:
        """Valid MP4 content named with unknown extension .dat."""
        dat_file = tmp_path / "video.dat"
        dat_file.write_bytes(SAMPLE_HEADERS["mp4"])

        res = detect(dat_file)
        assert res == "mp4"
        assert len(res.warnings) == 1
        assert ".dat" in res.warnings[0]

    def test_extension_fallback_adds_warning(self, tmp_path: Path) -> None:
        """File with unrecognizable magic bytes falls back to extension with a warning."""
        fallback_file = tmp_path / "audio.mp3"
        fallback_file.write_bytes(b"Unrecognized bytes that don't match standard MP3 header")

        res = detect(fallback_file)
        assert res == "mp3"
        assert len(res.warnings) == 1
        assert "falling back to extension" in res.warnings[0]
