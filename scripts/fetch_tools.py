"""Fetch and verify external vendor binaries for Cuttle.

Reads scripts/tools.lock.toml, downloads external tools (FFmpeg, Pandoc) into
vendor/, verifies SHA-256 checksums, and extracts the required executables.
Refuses to extract or use files with mismatched checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path


class ChecksumMismatchError(Exception):
    """Raised when a downloaded file does not match its expected SHA-256 hash."""


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute the SHA-256 hex digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checksum(file_path: Path, expected_hash: str) -> bool:
    """Verify that a file's SHA-256 matches the expected hash (case-insensitive)."""
    computed = compute_sha256(file_path)
    return computed.lower() == expected_hash.strip().lower()


def load_tools_lock(lockfile_path: Path) -> dict[str, dict]:
    """Load and parse tools.lock.toml."""
    if not lockfile_path.is_file():
        raise FileNotFoundError(f"Tools lockfile not found: {lockfile_path}")
    with open(lockfile_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tools", {})


def download_file(url: str, dest_path: Path, chunk_size: int = 1048576) -> None:
    """Download a file from url to dest_path with progress indication."""
    print(f"Downloading from {url} ...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dest = dest_path.with_suffix(".download")

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Cuttle-Tool-Fetcher/1.0"},
    )
    with urllib.request.urlopen(req) as response, open(temp_dest, "wb") as out_file:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        while chunk := response.read(chunk_size):
            out_file.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = (downloaded / total) * 100
                mb_down = downloaded / 1024 / 1024
                mb_total = total / 1024 / 1024
                print(
                    f"\r  {mb_down:.1f} MB / {mb_total:.1f} MB ({percent:.0f}%)",
                    end="",
                    flush=True,
                )
        print()

    temp_dest.replace(dest_path)


def extract_binaries_from_zip(
    archive_path: Path,
    target_binaries: list[str],
    vendor_dir: Path,
) -> list[Path]:
    """Extract specified binary names from a zip archive into vendor_dir."""
    vendor_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(archive_path, "r") as z:
        namelist = z.namelist()
        for target in target_binaries:
            # Match by basename (e.g. ffmpeg.exe inside subdirs)
            matching = [n for n in namelist if Path(n).name.lower() == target.lower()]
            if not matching:
                raise FileNotFoundError(f"Binary {target!r} not found in {archive_path.name}")

            source_entry = matching[0]
            out_path = vendor_dir / target
            print(f"Extracting {target} from {source_entry} ...")
            with z.open(source_entry) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(out_path)

    return extracted


def fetch_tool(
    tool_key: str,
    tool_config: dict,
    vendor_dir: Path,
    cache_archive: Path | None = None,
) -> list[Path]:
    """Fetch, verify, and extract a single tool definition.

    Raises ChecksumMismatchError if the archive checksum fails.
    """
    url = tool_config["url"]
    expected_sha256 = tool_config["sha256"]
    binaries = tool_config.get("binaries", [])

    archive_name = Path(url).name
    archive_path = cache_archive or (vendor_dir / archive_name)

    # If archive doesn't exist or hash is bad, download it
    need_download = True
    if archive_path.exists():
        print(f"Checking existing archive: {archive_path.name} ...")
        if verify_checksum(archive_path, expected_sha256):
            print("  Checksum verified for cached archive.")
            need_download = False
        else:
            print("  Cached archive checksum mismatch. Re-downloading...")
            archive_path.unlink()

    if need_download:
        download_file(url, archive_path)
        print("Verifying downloaded file checksum...")
        if not verify_checksum(archive_path, expected_sha256):
            actual_sha256 = compute_sha256(archive_path)
            archive_path.unlink(missing_ok=True)
            raise ChecksumMismatchError(
                f"Checksum mismatch for {archive_name}:\n"
                f"  Expected: {expected_sha256}\n"
                f"  Actual:   {actual_sha256}"
            )
        print("  Checksum OK.")

    # Extract binaries
    if archive_path.suffix.lower() == ".zip":
        return extract_binaries_from_zip(archive_path, binaries, vendor_dir)
    else:
        raise NotImplementedError(f"Unsupported archive format: {archive_path.suffix}")


def main() -> int:
    """CLI entry point for scripts/fetch_tools.py."""
    parser = argparse.ArgumentParser(description="Fetch and verify Cuttle external vendor tools.")
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=Path(__file__).parent / "tools.lock.toml",
        help="Path to tools.lock.toml",
    )
    parser.add_argument(
        "--vendor-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "vendor",
        help="Destination vendor directory",
    )
    args = parser.parse_args()

    try:
        tools = load_tools_lock(args.lockfile)
        if not tools:
            print("No tools defined in lockfile.")
            return 0

        args.vendor_dir.mkdir(parents=True, exist_ok=True)
        for tool_name, tool_cfg in tools.items():
            print(f"\n--- Processing {tool_name} ---")
            extracted = fetch_tool(tool_name, tool_cfg, args.vendor_dir)
            for path in extracted:
                print(f"  Installed: {path}")

        print("\nAll tools fetched and verified successfully.")
        return 0
    except ChecksumMismatchError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
