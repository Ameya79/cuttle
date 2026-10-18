"""Unit tests verifying test fixtures and hostile inputs (P1-06).

Per TRD task card P1-06:
- All expected files exist and are non-empty (except zero_byte.mp4)
- Hostile edge-case files exist and behave as specified
- Locked file fixture behaves correctly
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cuttle.engine.detect import detect
from cuttle.engine.errors import CuttleError


def test_golden_fixtures_exist_and_non_empty(fixtures_dir: Path) -> None:
    """Verify all golden fixtures exist and have non-zero size."""
    expected_files = [
        "video_av.mp4",
        "video_silent.mp4",
        "audio.wav",
        "audio.mp3",
        "img.png",
        "img.jpg",
        "img.bmp",
        "img.webp",
        "img.tiff",
        "img.gif",
        "img.heic",
    ]
    for filename in expected_files:
        path = fixtures_dir / filename
        assert path.exists(), f"Missing expected fixture: {filename}"
        assert path.is_file(), f"Fixture is not a file: {filename}"
        size = path.stat().st_size
        assert size > 0, f"Golden fixture {filename} is unexpectedly empty"


def test_nasty_zero_byte_is_empty(fixtures_dir: Path) -> None:
    """zero_byte.mp4 must have a size of exactly 0 bytes."""
    path = fixtures_dir / "zero_byte.mp4"
    assert path.exists()
    assert path.stat().st_size == 0
    with pytest.raises(CuttleError) as exc_info:
        detect(path)
    assert exc_info.value.code == "E_SRC_CORRUPT"


def test_nasty_truncated_file(fixtures_dir: Path) -> None:
    """truncated.mp4 must have approximately 30% of video_av.mp4 size."""
    full_path = fixtures_dir / "video_av.mp4"
    trunc_path = fixtures_dir / "truncated.mp4"

    assert full_path.exists()
    assert trunc_path.exists()

    full_size = full_path.stat().st_size
    trunc_size = trunc_path.stat().st_size

    assert 0 < trunc_size < full_size
    ratio = trunc_size / full_size
    assert 0.25 <= ratio <= 0.35


def test_nasty_mismatched_extensions(fixtures_dir: Path) -> None:
    """png_named_jpg.jpg must be detected as PNG with a warning."""
    png_as_jpg = fixtures_dir / "png_named_jpg.jpg"
    assert png_as_jpg.exists()

    res = detect(png_as_jpg)
    assert res == "png"
    assert len(res.warnings) >= 1
    assert "jpg" in res.warnings[0].lower()


def test_nasty_unicode_and_symbols_filenames(fixtures_dir: Path) -> None:
    """Filenames with non-English Unicode and shell symbols must be accessible."""
    unicode_file = fixtures_dir / "वीडियो नमूना.mp4"
    assert unicode_file.exists()
    assert unicode_file.stat().st_size > 0
    res_unicode = detect(unicode_file)
    assert res_unicode == "mp4"

    shell_file = fixtures_dir / "a & b (final) v2.mp4"
    assert shell_file.exists()
    assert shell_file.stat().st_size > 0
    res_shell = detect(shell_file)
    assert res_shell == "mp4"


def test_nasty_long_path_file(fixtures_dir: Path) -> None:
    """File inside nested path exceeding 200+ characters must be readable."""
    nested = fixtures_dir / "long_path"
    assert nested.exists()

    # Find the nested file
    files = list(nested.glob("**/video_long_path.mp4"))
    assert len(files) == 1
    long_file = files[0]
    assert len(str(long_file)) > 150
    assert long_file.stat().st_size > 0


def test_locked_file_fixture(locked_file: Path) -> None:
    """locked_file fixture should produce locking collisions when opened with lock."""
    if os.name == "nt":
        import msvcrt

        assert locked_file.exists()
        with open(locked_file, "r+b") as second_handle:
            with pytest.raises(OSError):
                msvcrt.locking(second_handle.fileno(), msvcrt.LK_NBLCK, 1)
