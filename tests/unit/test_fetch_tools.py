"""Unit tests for scripts/fetch_tools.py (P1-02).

Per TRD task card P1-02:
- Reads scripts/tools.lock.toml
- Verifies SHA-256 checksums
- Refuses on mismatch
- Tests must NOT perform real network downloads
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.fetch_tools import (
    ChecksumMismatchError,
    compute_sha256,
    extract_binaries_from_zip,
    fetch_tool,
    load_tools_lock,
    verify_checksum,
)


def test_compute_sha256(tmp_path: Path) -> None:
    content = b"hello cuttle world"
    expected = hashlib.sha256(content).hexdigest()
    test_file = tmp_path / "sample.bin"
    test_file.write_bytes(content)

    assert compute_sha256(test_file) == expected


def test_verify_checksum_matches(tmp_path: Path) -> None:
    content = b"valid content"
    expected = hashlib.sha256(content).hexdigest()
    test_file = tmp_path / "valid.bin"
    test_file.write_bytes(content)

    assert verify_checksum(test_file, expected) is True
    assert verify_checksum(test_file, expected.upper()) is True


def test_verify_checksum_mismatch(tmp_path: Path) -> None:
    content = b"valid content"
    wrong_hash = "0" * 64
    test_file = tmp_path / "valid.bin"
    test_file.write_bytes(content)

    assert verify_checksum(test_file, wrong_hash) is False


def test_load_tools_lock() -> None:
    lockfile = Path(__file__).resolve().parent.parent.parent / "scripts" / "tools.lock.toml"
    assert lockfile.exists()

    tools = load_tools_lock(lockfile)
    assert "ffmpeg" in tools
    assert "url" in tools["ffmpeg"]
    assert "sha256" in tools["ffmpeg"]
    assert len(tools["ffmpeg"]["sha256"]) == 64
    assert "binaries" in tools["ffmpeg"]


def test_extract_binaries_from_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "mock_tool.zip"
    vendor_dir = tmp_path / "vendor"

    # Create a mock zip with nested structure
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("tool-1.0/bin/ffmpeg.exe", b"dummy ffmpeg binary")
        z.writestr("tool-1.0/bin/ffprobe.exe", b"dummy ffprobe binary")
        z.writestr("tool-1.0/doc/readme.txt", b"docs")

    extracted = extract_binaries_from_zip(
        zip_path,
        ["ffmpeg.exe", "ffprobe.exe"],
        vendor_dir,
    )

    assert len(extracted) == 2
    assert (vendor_dir / "ffmpeg.exe").read_bytes() == b"dummy ffmpeg binary"
    assert (vendor_dir / "ffprobe.exe").read_bytes() == b"dummy ffprobe binary"


def test_extract_missing_binary_raises(tmp_path: Path) -> None:
    zip_path = tmp_path / "mock_tool.zip"
    vendor_dir = tmp_path / "vendor"

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("tool-1.0/bin/other.exe", b"data")

    with pytest.raises(FileNotFoundError, match="not found in"):
        extract_binaries_from_zip(zip_path, ["ffmpeg.exe"], vendor_dir)


def test_fetch_tool_rejects_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vendor_dir = tmp_path / "vendor"
    vendor_dir.mkdir()

    # Create mock corrupted archive
    fake_zip = vendor_dir / "tool.zip"
    fake_zip.write_bytes(b"tampered or corrupted zip")

    tool_cfg = {
        "url": "https://example.com/tool.zip",
        "sha256": "1" * 64,  # doesn't match fake_zip
        "binaries": ["ffmpeg.exe"],
    }

    # Simulate download producing the fake file
    def mock_download(url: str, dest: Path) -> None:
        dest.write_bytes(b"corrupted content from network")

    monkeypatch.setattr("scripts.fetch_tools.download_file", mock_download)

    with pytest.raises(ChecksumMismatchError, match="Checksum mismatch"):
        fetch_tool("test_tool", tool_cfg, vendor_dir, cache_archive=fake_zip)


def test_fetch_tool_succeeds_with_valid_archive(tmp_path: Path) -> None:
    vendor_dir = tmp_path / "vendor"
    vendor_dir.mkdir()

    # Create a real valid zip
    valid_zip = vendor_dir / "valid_tool.zip"
    with zipfile.ZipFile(valid_zip, "w") as z:
        z.writestr("bin/ffmpeg.exe", b"executable bytes")

    valid_hash = hashlib.sha256(valid_zip.read_bytes()).hexdigest()

    tool_cfg = {
        "url": "https://example.com/valid_tool.zip",
        "sha256": valid_hash,
        "binaries": ["ffmpeg.exe"],
    }

    extracted = fetch_tool("test_tool", tool_cfg, vendor_dir, cache_archive=valid_zip)
    assert len(extracted) == 1
    assert (vendor_dir / "ffmpeg.exe").read_bytes() == b"executable bytes"
