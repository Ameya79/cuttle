"""Safe output filesystem helpers.

Implements TRD §6.5 steps 3, 4, 5, 8:
- free_name: collision-avoiding naming: (converted), (converted) (2), (converted) (3)
- check_free_space: validates disk space >= 2 * source size
- temp_output: context manager guaranteeing .cuttle-part deletion on exit
- commit_output: rename loop handling FileExistsError races without overwriting existing files
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil

from cuttle.engine.errors import CuttleError

PART_SUFFIX = ".cuttle-part"


def free_name(out_dir: Path, stem: str, ext: str) -> Path:
    """Find the next available filename that does not exist in out_dir.

    Naming sequence:
      1. '<stem> (converted).<ext>'
      2. '<stem> (converted) (2).<ext>'
      3. '<stem> (converted) (3).<ext>'
      ...
    """
    clean_ext = ext.lstrip(".").lower()
    candidate = out_dir / f"{stem} (converted).{clean_ext}"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = out_dir / f"{stem} (converted) ({counter}).{clean_ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def check_free_space(out_dir: Path, required_bytes: int) -> None:
    """Ensure out_dir's filesystem has at least required_bytes free space.

    Raises CuttleError("E_DISK_SPACE") if insufficient space.
    """
    try:
        usage = shutil.disk_usage(out_dir)
        free = usage.free
    except OSError as err:
        # If disk usage cannot be determined, proceed cautiously
        return

    if free < required_bytes:
        req_mb = required_bytes / 1024 / 1024
        free_mb = free / 1024 / 1024
        raise CuttleError(
            code="E_DISK_SPACE",
            user_message=(
                f"Not enough free disk space. Requires at least {req_mb:.1f} MB, "
                f"but only {free_mb:.1f} MB is available."
            ),
            detail=f"Free bytes: {free}, Required bytes: {required_bytes}, Target dir: {out_dir}",
        )


@contextmanager
def temp_output(final_path: Path) -> Generator[Path, None, None]:
    """Context manager providing a temporary output path with .cuttle-part extension.

    Guarantees that the temporary file is deleted on any exception, return, or cancel.
    """
    tmp_path = final_path.with_name(final_path.name + PART_SUFFIX)
    try:
        yield tmp_path
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def commit_output(
    tmp_path: Path,
    out_dir: Path,
    stem: str,
    ext: str,
    max_retries: int = 50,
) -> Path:
    """Atomically commit a temporary output file to its final free destination name.

    Per TRD §6.5 step 8:
    Uses os.rename (never overwriting existing files).
    If a race condition occurs and the chosen name appears concurrently,
    catches FileExistsError and retries with the next free name.
    """
    clean_ext = ext.lstrip(".").lower()
    for _ in range(max_retries):
        target = free_name(out_dir, stem, clean_ext)
        try:
            os.rename(tmp_path, target)
            return target
        except FileExistsError:
            # Another process created this file in the race window; pick next free name
            continue

    raise CuttleError(
        code="E_TOOL_FAILED",
        user_message="Could not commit converted file due to repeated filename conflicts.",
        detail=f"Exceeded {max_retries} rename attempts in {out_dir}",
    )
