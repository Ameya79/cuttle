"""Unit tests for the in-app update check subsystem (P6-06).

Per TRD task card P6-06:
- Checks GitHub Releases API for newer version.
- Compares semantic versions.
- Verifies SHA256 hashes against SHA256SUMS.txt.
- Respects 24-hour cache cooldown.
- Engine makes zero network calls (strictly worker layer).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from cuttle.worker.updater import (
    UpdateInfo,
    check_for_updates,
    is_newer_version,
    parse_sha256sums,
    parse_version_tuple,
    verify_file_sha256,
)


def test_version_parsing_and_comparison() -> None:
    """Test version string parsing and semantic comparison."""
    assert parse_version_tuple("v1.2.3") == (1, 2, 3)
    assert parse_version_tuple("0.5.0") == (0, 5, 0)
    assert parse_version_tuple("1.0") == (1, 0, 0)
    assert parse_version_tuple("v2.1.0-beta") == (2, 1, 0)

    assert is_newer_version("1.0.0", "0.5.0") is True
    assert is_newer_version("0.5.1", "0.5.0") is True
    assert is_newer_version("0.5.0", "0.5.0") is False
    assert is_newer_version("0.4.9", "0.5.0") is False
    assert is_newer_version("v1.0.0", "0.9.9") is True


def test_sha256sums_parsing_and_verification(tmp_path: Path) -> None:
    """Test parsing SHA256SUMS.txt and verifying file integrity."""
    sample_text = (
        "# Checksums for Cuttle v1.0.0\n"
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty.txt\n"
        "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae *cuttle-setup-x64.exe\n"
    )
    mapping = parse_sha256sums(sample_text)
    expected_empty = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    expected_setup = "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
    assert mapping["empty.txt"] == expected_empty
    assert mapping["cuttle-setup-x64.exe"] == expected_setup

    # Test file verification
    test_file = tmp_path / "hello.bin"
    test_content = b"Cuttle test binary payload"
    test_file.write_bytes(test_content)
    real_hash = hashlib.sha256(test_content).hexdigest()

    assert verify_file_sha256(test_file, real_hash) is True
    assert verify_file_sha256(test_file, "wrong_hash_digest") is False
    assert verify_file_sha256(tmp_path / "nonexistent.bin", real_hash) is False


def test_check_for_updates_with_newer_release(tmp_path: Path) -> None:
    """When remote version is newer, check_for_updates returns UpdateInfo and caches it."""
    cache_path = tmp_path / "update_cache.json"

    fake_release_payload = {
        "tag_name": "v1.2.0",
        "body": "Major performance improvements and new CAD features.",
        "html_url": "https://github.com/Ameya79/cuttle/releases/tag/v1.2.0",
        "published_at": "2026-10-20T00:00:00Z",
        "assets": [
            {
                "name": "cuttle-setup-x64.exe",
                "browser_download_url": "https://example.com/cuttle-setup-x64.exe",
            },
            {
                "name": "cuttle-portable-x64.zip",
                "browser_download_url": "https://example.com/cuttle-portable-x64.zip",
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://example.com/SHA256SUMS.txt",
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_release_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = check_for_updates(
            current_version="1.0.0",
            force=True,
            cache_path=cache_path,
        )

    assert info is not None
    assert isinstance(info, UpdateInfo)
    assert info.version == "1.2.0"
    assert info.installer_url == "https://example.com/cuttle-setup-x64.exe"
    assert info.portable_url == "https://example.com/cuttle-portable-x64.zip"
    assert info.checksums_url == "https://example.com/SHA256SUMS.txt"
    assert cache_path.is_file()

    # Second check within cooldown should hit cache without network
    with patch("urllib.request.urlopen") as mock_url:
        cached_info = check_for_updates(
            current_version="1.0.0",
            force=False,
            cache_path=cache_path,
        )
        assert cached_info is not None
        assert cached_info.version == "1.2.0"
        mock_url.assert_not_called()


def test_check_for_updates_when_up_to_date(tmp_path: Path) -> None:
    """When remote version is equal or older, check_for_updates returns None."""
    cache_path = tmp_path / "update_cache.json"

    fake_release_payload = {
        "tag_name": "v1.0.0",
        "body": "Current release",
        "assets": [],
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(fake_release_payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        info = check_for_updates(
            current_version="1.0.0",
            force=True,
            cache_path=cache_path,
        )

    assert info is None


def test_check_for_updates_network_error_graceful(tmp_path: Path) -> None:
    """Network timeouts and errors must degrade gracefully returning None."""
    cache_path = tmp_path / "update_cache.json"

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Network timed out")):
        info = check_for_updates(
            current_version="1.0.0",
            force=True,
            cache_path=cache_path,
        )
    assert info is None
