"""Tests for safe_output.py (P1-07).

Per TRD task card P1-07:
- Name collisions produce (converted), (2), (3)
- Simulated FileExistsError race picks the next free name
- Temp file is removed on exception and on cancel
- os.replace is never called (grep test and mock assertion)
- check_free_space raises E_DISK_SPACE when space is insufficient
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cuttle.engine.errors import CuttleError
from cuttle.engine.safe_output import (
    PART_SUFFIX,
    check_free_space,
    commit_output,
    free_name,
    temp_output,
)


def test_free_name_no_collision(tmp_path: Path) -> None:
    first = free_name(tmp_path, "sample", "mp3")
    assert first.name == "sample (converted).mp3"
    assert not first.exists()


def test_free_name_collisions_produce_sequence(tmp_path: Path) -> None:
    """Collisions sequentially generate (converted), (2), (3), (4)."""
    # 1. No collision -> sample (converted).mp3
    p1 = free_name(tmp_path, "sample", "mp3")
    assert p1.name == "sample (converted).mp3"
    p1.touch()

    # 2. Collision with p1 -> sample (converted) (2).mp3
    p2 = free_name(tmp_path, "sample", "mp3")
    assert p2.name == "sample (converted) (2).mp3"
    p2.touch()

    # 3. Collision with p1, p2 -> sample (converted) (3).mp3
    p3 = free_name(tmp_path, "sample", "mp3")
    assert p3.name == "sample (converted) (3).mp3"
    p3.touch()

    # 4. Collision with p1, p2, p3 -> sample (converted) (4).mp3
    p4 = free_name(tmp_path, "sample", "mp3")
    assert p4.name == "sample (converted) (4).mp3"


def test_check_free_space_sufficient(tmp_path: Path) -> None:
    # 1 KB required should succeed on any functioning test machine
    check_free_space(tmp_path, 1024)


def test_check_free_space_insufficient_raises_e_disk_space(tmp_path: Path) -> None:
    fake_usage = MagicMock(free=500)
    with patch("shutil.disk_usage", return_value=fake_usage):
        with pytest.raises(CuttleError) as exc_info:
            check_free_space(tmp_path, required_bytes=1000)
        assert exc_info.value.code == "E_DISK_SPACE"
        assert "free disk space" in exc_info.value.user_message.lower()


def test_temp_output_removes_file_on_normal_exit(tmp_path: Path) -> None:
    final = tmp_path / "out.mp4"
    with temp_output(final) as tmp:
        assert tmp.name == "out.mp4" + PART_SUFFIX
        tmp.write_bytes(b"temporary work")
        assert tmp.exists()

    # Once context exits, tmp must be deleted
    assert not tmp.exists()


def test_temp_output_removes_file_on_exception(tmp_path: Path) -> None:
    final = tmp_path / "out.mp4"
    with pytest.raises(RuntimeError, match="simulated failure"):
        with temp_output(final) as tmp:
            tmp.write_bytes(b"in-progress conversion before crash")
            assert tmp.exists()
            raise RuntimeError("simulated failure")

    # Guarantees no .cuttle-part remains after exception
    assert not tmp.exists()


def test_commit_output_success(tmp_path: Path) -> None:
    final_target = tmp_path / "test.mp3"
    tmp_file = tmp_path / ("test.mp3" + PART_SUFFIX)
    tmp_file.write_bytes(b"converted mp3 audio data")

    committed = commit_output(tmp_file, tmp_path, "test", "mp3")
    assert committed.name == "test (converted).mp3"
    assert committed.exists()
    assert committed.read_bytes() == b"converted mp3 audio data"
    assert not tmp_file.exists()


def test_commit_output_simulated_file_exists_race(tmp_path: Path) -> None:
    """When a concurrent race condition creates the first chosen name, commit_output picks next free name."""
    tmp_file = tmp_path / ("race.mp3" + PART_SUFFIX)
    tmp_file.write_bytes(b"data")

    original_rename = os.rename
    attempt_count = 0

    def mock_rename(src: str | Path, dst: str | Path) -> None:
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            # Simulate collision on first attempt
            (tmp_path / "race (converted).mp3").touch()
            raise FileExistsError("WinError 183: Cannot create a file when that file already exists")
        original_rename(src, dst)

    with patch("os.rename", side_effect=mock_rename):
        committed = commit_output(tmp_file, tmp_path, "race", "mp3")

    assert committed.name == "race (converted) (2).mp3"
    assert committed.exists()
    assert attempt_count == 2


def test_os_replace_is_never_called(tmp_path: Path) -> None:
    """Hard rule: os.replace must never be called in safe_output.py."""
    # 1. Grep test
    src_file = (
        Path(__file__).resolve().parent.parent.parent
        / "cuttle"
        / "engine"
        / "safe_output.py"
    )
    content = src_file.read_text(encoding="utf-8")
    assert "os.replace" not in content

    # 2. Mock guard test during execution
    tmp_file = tmp_path / ("guard.mp4" + PART_SUFFIX)
    tmp_file.write_bytes(b"payload")

    with patch("os.replace", side_effect=AssertionError("os.replace must never be called!")):
        committed = commit_output(tmp_file, tmp_path, "guard", "mp4")

    assert committed.exists()
