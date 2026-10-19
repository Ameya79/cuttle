"""Unit tests for folder batch scanning and conversion.

Per task card P3-06:
- Nested folders traversal
- Extension filters
- Rejection of symlink escapes
- Skipping of '(converted)' files
- 200 small files with unified summary
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from cuttle.engine.folder import (
    convert_folder,
    gather_folder_files,
    is_safe_contained_path,
)
from cuttle.engine.types import ConvertResult, Quality


class TestFolderFileGathering:
    def test_gather_nested_and_skip_converted(self, tmp_path: Path) -> None:
        root = tmp_path / "documents"
        sub = root / "subfolder"
        sub.mkdir(parents=True)

        f1 = root / "file1.md"
        f1.write_text("content1", encoding="utf-8")
        f2 = sub / "file2.md"
        f2.write_text("content2", encoding="utf-8")

        # Converted and temp files to skip
        f_conv = root / "file1 (converted).docx"
        f_conv.write_text("skip me", encoding="utf-8")
        f_part = root / "file3.md.cuttle-part"
        f_part.write_text("skip me", encoding="utf-8")

        gathered = gather_folder_files(root, recursive=True)
        assert f1 in gathered
        assert f2 in gathered
        assert f_conv not in gathered
        assert f_part not in gathered
        assert len(gathered) == 2

    def test_non_recursive_gathering(self, tmp_path: Path) -> None:
        root = tmp_path / "flat"
        sub = root / "nested"
        sub.mkdir(parents=True)

        top_file = root / "top.txt"
        top_file.write_text("top", encoding="utf-8")
        nested_file = sub / "nested.txt"
        nested_file.write_text("nested", encoding="utf-8")

        gathered = gather_folder_files(root, recursive=False)
        assert top_file in gathered
        assert nested_file not in gathered
        assert len(gathered) == 1

    def test_extension_filter(self, tmp_path: Path) -> None:
        root = tmp_path / "mixed"
        root.mkdir()

        (root / "a.md").write_text("a", encoding="utf-8")
        (root / "b.html").write_text("b", encoding="utf-8")
        (root / "c.png").write_bytes(b"c")

        gathered = gather_folder_files(root, ext_filter={"md", "html"})
        names = {p.name for p in gathered}
        assert names == {"a.md", "b.html"}

    def test_symlink_escape_rejection(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        secret_file = outside / "secret.txt"
        secret_file.write_text("secret", encoding="utf-8")

        root = tmp_path / "inside"
        root.mkdir()

        # Test is_safe_contained_path
        assert is_safe_contained_path(root / "valid.txt", root) is True
        assert is_safe_contained_path(secret_file, root) is False

        # Attempt to create a symlink pointing outside if system permits
        link_dir = root / "symlink_out"
        try:
            os.symlink(str(outside), str(link_dir), target_is_directory=True)
            gathered = gather_folder_files(root, recursive=True)
            assert secret_file not in gathered
            assert not any(p.name == "secret.txt" for p in gathered)
        except (OSError, NotImplementedError):
            # Non-admin Windows without developer mode may disallow symlink creation
            pass


class TestFolderConversionExecution:
    def test_200_small_files_summary(self, tmp_path: Path) -> None:
        root = tmp_path / "batch200"
        root.mkdir()

        total = 200
        for i in range(total):
            f = root / f"file_{i:03d}.txt"
            f.write_text(f"text {i}", encoding="utf-8")

        mock_convert_result = ConvertResult(
            output=tmp_path / "converted.docx",
            quality=Quality.LOSSLESS,
            warnings=[],
        )

        with patch("cuttle.engine.folder.convert", return_value=mock_convert_result):
            res = convert_folder(root, "docx")

        assert res.total_files == 200
        assert res.succeeded == 200
        assert res.failed == 0
        assert res.skipped == 0
        assert len(res.results) == 200
