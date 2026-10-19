"""Folder conversion engine for batch processing directories.

Per task card P3-06:
- Supports recursive (default True) or flat folder scanning.
- Filters by extension when requested.
- Skips already converted files ('(converted)' in stem).
- Strict defense against symlink and NTFS junction escapes (never traverses outside root).
- Provides conversion summary across all processed files.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from cuttle.engine.convert import convert
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, ConvertResult


@dataclass
class FolderResult:
    """Summary of batch folder conversion."""

    total_files: int
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[ConvertResult] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def is_symlink_or_junction(path: Path) -> bool:
    """Check if path is a symlink or Windows NTFS directory junction."""
    if path.is_symlink():
        return True
    try:
        # Check FILE_ATTRIBUTE_REPARSE_POINT on Windows
        stat_res = os.lstat(path)
        return bool(getattr(stat_res, "st_file_attributes", 0) & 0x00000400)
    except (OSError, AttributeError):
        return False


def is_safe_contained_path(candidate: Path, base_folder: Path) -> bool:
    """Verify that candidate path resolves strictly within the base folder boundary."""
    try:
        base_real = base_folder.resolve()
        candidate_real = candidate.resolve()
        candidate_real.relative_to(base_real)
        return True
    except (ValueError, OSError):
        return False


def gather_folder_files(
    folder: Path,
    recursive: bool = True,
    ext_filter: set[str] | list[str] | None = None,
) -> list[Path]:
    """Scan directory and gather eligible files safely without escaping boundaries.

    Parameters:
        folder: Root directory to scan.
        recursive: If True, recursively scan subdirectories.
        ext_filter: Optional set of allowed file extensions (without dots).

    Returns:
        List of regular file Paths eligible for conversion.
    """
    base = folder.resolve()
    if not base.is_dir():
        raise CuttleError(
            code="E_SRC_MISSING",
            user_message=f"Directory not found: {folder.name}",
            detail=f"Path is not an existing directory: {folder}",
        )

    clean_filter = {e.lower().lstrip(".") for e in ext_filter} if ext_filter else None
    gathered: list[Path] = []

    def scan_dir(current_dir: Path) -> None:
        try:
            entries = sorted(current_dir.iterdir())
        except OSError:
            return

        for entry in entries:
            # Prevent following symlinks or junctions that escape base folder
            if is_symlink_or_junction(entry) and not is_safe_contained_path(entry, base):
                continue

            if entry.is_file():
                # Skip temp and partially converted files
                if entry.name.endswith(".cuttle-part"):
                    continue

                # Skip files already marked as converted
                if "(converted)" in entry.stem:
                    continue

                # Check extension filter
                if clean_filter is not None:
                    ext = entry.suffix.lower().lstrip(".")
                    if ext not in clean_filter:
                        continue

                gathered.append(entry)

            elif entry.is_dir() and recursive:
                # Do not follow symlinks/junctions outside base folder
                if is_symlink_or_junction(entry) and not is_safe_contained_path(entry, base):
                    continue
                scan_dir(entry)

    scan_dir(base)
    return gathered


def convert_folder(
    folder: Path,
    dst_fmt: str,
    out_dir: Path | None = None,
    recursive: bool = True,
    ext_filter: set[str] | list[str] | None = None,
    cancel: CancelToken | None = None,
    on_file_done: Callable[[Path, bool, str], None] | None = None,
) -> FolderResult:
    """Convert all convertible files in folder to the target format."""
    files = gather_folder_files(folder, recursive=recursive, ext_filter=ext_filter)
    summary = FolderResult(total_files=len(files))

    cancel_tok = cancel or CancelToken()

    for f in files:
        if cancel_tok.cancelled:
            break

        try:
            # Place output in target out_dir if specified, else next to source
            target_out = out_dir if out_dir else f.parent
            res = convert(f, dst_fmt, out_dir=target_out, cancel=cancel_tok)
            summary.succeeded += 1
            summary.results.append(res)
            if on_file_done:
                on_file_done(f, True, str(res.output))
        except CuttleError as err:
            if err.code == "E_UNSUPPORTED":
                summary.skipped += 1
            else:
                summary.failed += 1
                summary.errors.append((f, err.user_message))
            if on_file_done:
                on_file_done(f, False, err.user_message)
        except Exception as exc:
            summary.failed += 1
            summary.errors.append((f, str(exc)))
            if on_file_done:
                on_file_done(f, False, str(exc))

    return summary
