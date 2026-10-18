"""Pytest configuration and global test fixtures.

Per TRD §6.10:
- Provides fixtures_dir pointing to tests/fixtures/
- Automatically generates fixtures if missing
- Provides locked_file fixture for testing E_SRC_LOCKED
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import sys

import pytest

from tests.make_fixtures import generate_all_fixtures


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the absolute path to tests/fixtures, generating files if not present."""
    fix_dir = Path(__file__).resolve().parent / "fixtures"
    required = ["video_av.mp4", "img.png", "zero_byte.mp4"]
    if not fix_dir.is_dir() or not all((fix_dir / req).exists() for req in required):
        generate_all_fixtures(fix_dir)
    return fix_dir


@contextmanager
def acquire_file_lock(file_path: Path) -> Generator[Path, None, None]:
    """Exclusively lock a file handle to test concurrent access and E_SRC_LOCKED."""
    if sys.platform == "win32":
        import msvcrt

        f = open(file_path, "r+b")
        try:
            # Lock the first byte exclusively and non-blocking
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            yield file_path
        finally:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            f.close()
    else:
        import fcntl

        f = open(file_path, "r+b")
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield file_path
        finally:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            f.close()


@pytest.fixture
def locked_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary file locked exclusively by another handle."""
    target = tmp_path / "locked_sample.mp4"
    target.write_bytes(b"dummy locked content for testing E_SRC_LOCKED")
    with acquire_file_lock(target) as locked_path:
        yield locked_path
