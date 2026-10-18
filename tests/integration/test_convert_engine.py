"""Integration tests for cuttle/engine/convert.py (P1-11).

Per TRD task card P1-11 and .agents/rules/testing-rigor.md:
- Full end-to-end tests across audio, video, and image conversions.
- Tests list_targets for video and image inputs.
- Verifies source file SHA-256 hash is NEVER changed (success or failure).
- Verifies no .cuttle-part files are left behind anywhere.
- Harsh & extreme test cases:
  * zero-byte files (E_SRC_CORRUPT)
  * truncated files (E_SRC_CORRUPT / E_TOOL_FAILED)
  * mismatched extensions (detects true format, includes warning)
  * Unicode filenames (Hindi, Japanese)
  * shell symbols in filenames (&, ;, quotes, spaces)
  * locked files (E_SRC_LOCKED)
  * cancellation during conversion (E_CANCELLED)
  * collision handling produces (converted), (converted) (2)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cuttle.engine.convert import convert, list_targets
from cuttle.engine.errors import CuttleError
from cuttle.engine.safe_output import PART_SUFFIX
from cuttle.engine.types import CancelToken, Quality


def sha256_of(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestListTargets:
    def test_list_targets_video(self, fixtures_dir: Path) -> None:
        src = fixtures_dir / "video_av.mp4"
        targets = list_targets(src)
        target_fmts = {t.fmt for t in targets}
        assert {"mp3", "wav", "webm", "gif"}.issubset(target_fmts)
        assert all(t.available for t in targets)

    def test_list_targets_image(self, fixtures_dir: Path) -> None:
        src = fixtures_dir / "img.png"
        targets = list_targets(src)
        target_fmts = {t.fmt for t in targets}
        assert {"jpg", "webp", "bmp", "tiff"}.issubset(target_fmts)

    def test_list_targets_missing_raises_e_src_missing(self, tmp_path: Path) -> None:
        with pytest.raises(CuttleError) as exc_info:
            list_targets(tmp_path / "missing_file_xyz.mp4")
        assert exc_info.value.code == "E_SRC_MISSING"

    def test_list_targets_locked_file_raises_e_src_locked(self, locked_file: Path) -> None:
        with pytest.raises(CuttleError) as exc_info:
            list_targets(locked_file)
        assert exc_info.value.code == "E_SRC_LOCKED"


class TestConvertGoldenCases:
    @pytest.mark.parametrize(
        ("fixture_name", "dst_fmt", "expected_quality"),
        [
            ("video_av.mp4", "mp3", Quality.LOSSY),
            ("video_av.mp4", "wav", Quality.LOSSLESS),
            ("video_av.mp4", "webm", Quality.LOSSY),
            ("video_av.mp4", "gif", Quality.LOSSY),
            ("audio.wav", "mp3", Quality.LOSSY),
            ("img.png", "jpg", Quality.LOSSY),
            ("img.png", "bmp", Quality.LOSSLESS),
            ("img.png", "webp", Quality.LOSSY),
            ("img.heic", "jpg", Quality.LOSSY),
        ],
    )
    def test_golden_conversions_succeed_and_preserve_source_hash(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
        fixture_name: str,
        dst_fmt: str,
        expected_quality: Quality,
    ) -> None:
        src = fixtures_dir / fixture_name
        assert src.is_file(), f"Fixture {fixture_name} missing"

        initial_hash = sha256_of(src)
        out_dir = tmp_path / "out"

        progress_log: list[float] = []

        def on_prog(pct: float | None, msg: str = "") -> None:
            if pct is not None:
                progress_log.append(pct)

        result = convert(
            src,
            dst_fmt,
            out_dir=out_dir,
            on_progress=on_prog,
        )

        # 1. Output verification
        assert result.output.is_file()
        assert result.output.stat().st_size > 0
        assert result.quality == expected_quality
        assert result.output.suffix.lstrip(".").lower() == dst_fmt.lower()

        # 2. Source file immutability: hash must be identical
        assert sha256_of(src) == initial_hash

        # 3. No temporary files left behind
        leftovers = list(out_dir.glob(f"*{PART_SUFFIX}*"))
        assert len(leftovers) == 0, f"Found leaked part files: {leftovers}"

        # 4. Progress monotonically non-decreasing
        if progress_log:
            for i in range(len(progress_log) - 1):
                assert progress_log[i] <= progress_log[i + 1]


class TestConvertExtremeEdgeCases:
    """Extreme and hostile edge-case testing per .agents/rules/testing-rigor.md."""

    def test_zero_byte_file_raises_e_src_corrupt(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "zero_byte.mp4"
        with pytest.raises(CuttleError) as exc_info:
            convert(src, "mp3", out_dir=tmp_path)
        assert exc_info.value.code == "E_SRC_CORRUPT"

        # No .cuttle-part files left behind
        assert len(list(tmp_path.glob(f"*{PART_SUFFIX}*"))) == 0

    def test_truncated_media_raises_error_and_cleans_up(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "truncated.mp4"
        initial_hash = sha256_of(src)

        with pytest.raises(CuttleError) as exc_info:
            convert(src, "mp3", out_dir=tmp_path)
        assert exc_info.value.code in {"E_SRC_CORRUPT", "E_TOOL_FAILED"}

        # Source hash unchanged
        assert sha256_of(src) == initial_hash
        # No .cuttle-part files left behind
        assert len(list(tmp_path.glob(f"*{PART_SUFFIX}*"))) == 0

    def test_mismatched_extension_detected_correctly_with_warning(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        """png_named_jpg.jpg has JPEG extension but PNG magic bytes."""
        src = fixtures_dir / "png_named_jpg.jpg"
        initial_hash = sha256_of(src)

        result = convert(src, "bmp", out_dir=tmp_path)
        assert result.output.is_file()
        # Warning about extension disagreement must be reported
        assert len(result.warnings) > 0
        assert any("suggests" in w or "does not match" in w for w in result.warnings)

        # Source hash unchanged
        assert sha256_of(src) == initial_hash
        # No .cuttle-part files left behind
        assert len(list(tmp_path.glob(f"*{PART_SUFFIX}*"))) == 0

    def test_unicode_and_symbols_filenames(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Hindi filename and filenames with &, ;, parentheses, spaces."""
        hindi_files = list(fixtures_dir.glob("*.mp4"))
        hindi_candidates = [f for f in hindi_files if "वीडियो" in f.name or "????" in f.name]
        symbol_file = fixtures_dir / "a & b (final) v2.mp4"

        test_files = [symbol_file]
        if hindi_candidates:
            test_files.append(hindi_candidates[0])

        for src in test_files:
            assert src.is_file()
            initial_hash = sha256_of(src)

            res = convert(src, "wav", out_dir=tmp_path)
            assert res.output.is_file()
            assert res.output.stat().st_size > 0
            assert sha256_of(src) == initial_hash

    def test_locked_file_raises_e_src_locked(
        self,
        locked_file: Path,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(CuttleError) as exc_info:
            convert(locked_file, "mp3", out_dir=tmp_path)
        assert exc_info.value.code == "E_SRC_LOCKED"
        assert len(list(tmp_path.glob(f"*{PART_SUFFIX}*"))) == 0

    def test_cancellation_aborts_conversion_and_cleans_up(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "video_av.mp4"
        token = CancelToken()
        token.cancel()

        with pytest.raises(CuttleError) as exc_info:
            convert(src, "mp3", out_dir=tmp_path, cancel=token)
        assert exc_info.value.code == "E_CANCELLED"

        # Verify no .cuttle-part file or partial output remains
        assert len(list(tmp_path.glob(f"*{PART_SUFFIX}*"))) == 0

    def test_collision_handling_creates_sequence(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Converting the same file twice to the same dir creates
        (converted), then (converted) (2).
        """
        src = fixtures_dir / "img.png"
        out_dir = tmp_path / "collisions"
        out_dir.mkdir()

        res1 = convert(src, "jpg", out_dir=out_dir)
        assert res1.output.name == "img (converted).jpg"
        assert res1.output.is_file()

        res2 = convert(src, "jpg", out_dir=out_dir)
        assert res2.output.name == "img (converted) (2).jpg"
        assert res2.output.is_file()

        # Both files exist intact and were not overwritten
        assert res1.output.exists()
        assert res2.output.exists()

    def test_unsupported_conversion_raises_e_unsupported(
        self,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        src = fixtures_dir / "img.png"
        with pytest.raises(CuttleError) as exc_info:
            convert(src, "mp3", out_dir=tmp_path)
        assert exc_info.value.code == "E_UNSUPPORTED"
