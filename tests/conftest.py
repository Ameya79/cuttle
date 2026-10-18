"""Pytest configuration and global test fixtures.

Per TRD §6.10:
- Provides fixtures_dir pointing to tests/fixtures/
- Automatically generates fixtures if missing
- Provides locked_file fixture for testing E_SRC_LOCKED
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

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

        with open(file_path, "r+b") as f:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield file_path
            finally:
                with suppress(OSError):
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        with open(file_path, "r+b") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield file_path
            finally:
                with suppress(OSError):
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


@pytest.fixture
def locked_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a temporary file locked exclusively by another handle."""
    target = tmp_path / "locked_sample.mp4"
    target.write_bytes(b"dummy locked content for testing E_SRC_LOCKED")
    with acquire_file_lock(target) as locked_path:
        yield locked_path
