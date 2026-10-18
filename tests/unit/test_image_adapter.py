"""Unit and stress tests for cuttle/adapters/image.py (P1-10).

Per TRD task card P1-10 and .agents/rules/testing-rigor.md:
- Tests all supported source formats convert to valid targets and validate.
- Tests transparent PNG -> JPG and BMP flattens transparency to white.
- Tests EXIF orientation transposition.
- Tests HEIC -> JPG/PNG conversion.
- Extreme tests: zero-byte input, truncated input, garbage bytes, missing file.
- CancelToken cancellation behavior.
- Source file SHA-256 hash immutability verified across all tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from PIL import Image

from cuttle.adapters.image import ImageAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality


def sha256_of(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestImageAdapterCanConvert:
    @pytest.fixture
    def adapter(self) -> ImageAdapter:
        return ImageAdapter()

    def test_supported_targets(self, adapter: ImageAdapter) -> None:
        assert adapter.can_convert("png", "jpg") == Quality.LOSSY
        assert adapter.can_convert("png", "webp") == Quality.LOSSY
        assert adapter.can_convert("png", "bmp") == Quality.LOSSLESS
        assert adapter.can_convert("png", "tiff") == Quality.LOSSLESS
        assert adapter.can_convert("jpg", "png") == Quality.LOSSLESS
        assert adapter.can_convert("heic", "jpg") == Quality.LOSSY
        assert adapter.can_convert("heic", "png") == Quality.LOSSLESS
        assert adapter.can_convert("gif", "png") == Quality.LOSSLESS

    def test_unsupported_targets_return_none(self, adapter: ImageAdapter) -> None:
        assert adapter.can_convert("png", "mp4") is None
        assert adapter.can_convert("jpg", "pdf") is None
        assert adapter.can_convert("txt", "png") is None


class TestImageConversions:
    @pytest.fixture
    def adapter(self) -> ImageAdapter:
        return ImageAdapter()

    @pytest.mark.parametrize(
        ("src_name", "dst_fmt"),
        [
            ("img.png", "jpg"),
            ("img.png", "webp"),
            ("img.png", "bmp"),
            ("img.png", "tiff"),
            ("img.jpg", "png"),
            ("img.jpg", "webp"),
            ("img.jpg", "bmp"),
            ("img.jpg", "tiff"),
            ("img.webp", "png"),
            ("img.webp", "jpg"),
            ("img.webp", "bmp"),
            ("img.bmp", "png"),
            ("img.bmp", "jpg"),
            ("img.tiff", "png"),
            ("img.tiff", "jpg"),
            ("img.heic", "jpg"),
            ("img.heic", "png"),
            ("img.gif", "png"),
        ],
    )
    def test_golden_image_conversions_and_validation(
        self,
        adapter: ImageAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
        src_name: str,
        dst_fmt: str,
    ) -> None:
        """Every image fixture converts to target format and validates cleanly."""
        src = fixtures_dir / src_name
        assert src.is_file(), f"Fixture {src_name} not found"

        initial_hash = sha256_of(src)
        tmp_out = tmp_path / f"out_{src_name}.{dst_fmt}.cuttle-part"
        final_out = tmp_path / f"out_{src_name}.{dst_fmt}"

        progress_calls: list[tuple[float | None, str]] = []

        def on_prog(pct: float | None, msg: str = "") -> None:
            progress_calls.append((pct, msg))

        plan = adapter.plan(src, dst_fmt, tmp_out, {})
        adapter.run(plan, on_prog, CancelToken())

        assert tmp_out.is_file()
        assert tmp_out.stat().st_size > 0

        # Rename to final for validation
        tmp_out.rename(final_out)
        vr = adapter.validate(src, final_out)
        assert vr.ok is True, f"Validation failed: {vr.reason}"

        # Progress check: 0.0 -> 50.0 -> 100.0
        assert len(progress_calls) >= 3
        assert progress_calls[0][0] == 0.0
        assert progress_calls[-1][0] == 100.0

        # Source hash must remain 100% identical (immutable)
        assert sha256_of(src) == initial_hash

    def test_transparency_flattening_to_white(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        """Transparent pixels must flatten onto solid white (255, 255, 255) for JPG and BMP."""
        # Create a transparent PNG: red at (0, 0) with alpha=0, blue at (8, 8) with alpha=255
        src_png = tmp_path / "transparent_sample.png"
        img = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        img.putpixel((8, 8), (0, 0, 255, 255))
        img.save(src_png, format="PNG")

        initial_hash = sha256_of(src_png)

        for dst_fmt in ["jpg", "bmp"]:
            tmp_out = tmp_path / f"flat.{dst_fmt}.cuttle-part"
            final_out = tmp_path / f"flat.{dst_fmt}"

            plan = adapter.plan(src_png, dst_fmt, tmp_out, {})
            adapter.run(plan, lambda p, m="": None, CancelToken())
            tmp_out.rename(final_out)

            vr = adapter.validate(src_png, final_out)
            assert vr.ok is True

            with Image.open(final_out) as decoded:
                pixel_0_0 = decoded.getpixel((0, 0))
                # Must be white
                assert pixel_0_0[:3] == (255, 255, 255), (
                    f"Pixel (0,0) was {pixel_0_0}, expected white"
                )

        assert sha256_of(src_png) == initial_hash

    def test_exif_orientation_preservation(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        """EXIF orientation tag must be transposed into actual pixel data."""
        # Create an asymmetric image (20x10) with EXIF Orientation 6 (rotates 90 CW to 10x20)
        src_jpg = tmp_path / "oriented.jpg"
        im = Image.new("RGB", (20, 10), (100, 150, 200))
        exif = im.getexif()
        exif[0x0112] = 6  # Orientation tag = 6 (Rotate 90 CW)
        im.save(src_jpg, format="JPEG", exif=exif)

        tmp_out = tmp_path / "oriented_out.png.cuttle-part"
        final_out = tmp_path / "oriented_out.png"

        plan = adapter.plan(src_jpg, "png", tmp_out, {})
        adapter.run(plan, lambda p, m="": None, CancelToken())
        tmp_out.rename(final_out)

        with Image.open(final_out) as decoded:
            # Transposed 90 degrees CW swaps dimensions: (20, 10) becomes (10, 20)
            assert decoded.size == (10, 20)


class TestImageAdapterEdgeCases:
    """Extreme and hostile edge case testing per testing-rigor rule."""

    @pytest.fixture
    def adapter(self) -> ImageAdapter:
        return ImageAdapter()

    def test_zero_byte_file_raises_e_src_corrupt(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        zero_file = tmp_path / "zero_img.png"
        zero_file.write_bytes(b"")

        plan = adapter.plan(zero_file, "jpg", tmp_path / "out.jpg.cuttle-part", {})
        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda p, m="": None, CancelToken())
        assert exc_info.value.code == "E_SRC_CORRUPT"

    def test_truncated_image_raises_e_src_corrupt(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        # Partial PNG header
        trunc_file = tmp_path / "truncated_img.png"
        trunc_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")

        plan = adapter.plan(trunc_file, "jpg", tmp_path / "out.jpg.cuttle-part", {})
        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda p, m="": None, CancelToken())
        assert exc_info.value.code == "E_SRC_CORRUPT"

    def test_garbage_bytes_raises_e_src_corrupt(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        garbage_file = tmp_path / "garbage.jpg"
        garbage_file.write_bytes(b"NOT_AN_IMAGE_RANDOM_GARBAGE_PAYLOAD_1234567890" * 20)

        plan = adapter.plan(garbage_file, "png", tmp_path / "out.png.cuttle-part", {})
        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda p, m="": None, CancelToken())
        assert exc_info.value.code == "E_SRC_CORRUPT"

    def test_missing_source_file_raises_e_src_missing(
        self,
        adapter: ImageAdapter,
        tmp_path: Path,
    ) -> None:
        missing_file = tmp_path / "does_not_exist_9999.png"
        with pytest.raises(CuttleError) as exc_info:
            adapter.plan(missing_file, "jpg", tmp_path / "out.jpg.cuttle-part", {})
        assert exc_info.value.code == "E_SRC_MISSING"

    def test_cancel_before_run_raises_e_cancelled(
        self,
        adapter: ImageAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "img.png"
        tmp_out = tmp_path / "cancelled.jpg.cuttle-part"

        token = CancelToken()
        token.cancel()

        plan = adapter.plan(src, "jpg", tmp_out, {})
        with pytest.raises(CuttleError) as exc_info:
            adapter.run(plan, lambda p, m="": None, token)
        assert exc_info.value.code == "E_CANCELLED"
        assert not tmp_out.exists()

    def test_validation_detects_corrupt_or_zero_byte_output(
        self,
        adapter: ImageAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "img.png"
        zero_out = tmp_path / "zero_out.jpg"
        zero_out.write_bytes(b"")

        vr = adapter.validate(src, zero_out)
        assert vr.ok is False
        assert "0 bytes" in vr.reason

        corrupt_out = tmp_path / "corrupt_out.jpg"
        corrupt_out.write_bytes(b"CORRUPT_BYTES")
        vr2 = adapter.validate(src, corrupt_out)
        assert vr2.ok is False
        assert "validation failed" in vr2.reason.lower()
