"""In-app update check against GitHub Releases API (P6-06).

Per TRD task card P6-06:
- Checks GitHub Releases API for latest release tags.
- Verifies semantic versions and caches results to avoid spamming the API (24h cooldown).
- Verifies SHA-256 checksums against SHA256SUMS.txt.
- Triggers non-intrusive notification without automatically downloading or executing code.
- Strict architecture: Lives solely in the worker layer, engine makes zero network calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cuttle

logger = logging.getLogger(__name__)

DEFAULT_REPO = "Ameya79/cuttle"
GITHUB_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
DEFAULT_CHECK_INTERVAL_S = 86400  # 24 hours


@dataclass
class UpdateInfo:
    """Details of an available software update."""

    version: str
    release_notes: str
    html_url: str
    installer_url: str | None = None
    portable_url: str | None = None
    checksums_url: str | None = None
    published_at: str = ""


def get_default_update_cache_path() -> Path:
    """Return local path to the cached update status file."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "Cuttle" / "update_cache.json"


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a semantic version string (e.g. 'v1.2.3' or '0.5.0') into an integer tuple.

    Strips leading 'v' and ignores pre-release suffixes for basic numeric comparison.
    """
    clean = version_str.strip().lstrip("vV")
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", clean)
    if not match:
        return (0, 0, 0)
    parts = [int(group) for group in match.groups() if group is not None]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    """Return True if remote_version is strictly newer than current_version."""
    return parse_version_tuple(remote_version) > parse_version_tuple(current_version)


def parse_sha256sums(content: str) -> dict[str, str]:
    """Parse standard SHA256SUMS.txt file content into a filename-to-hash dictionary."""
    results: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            digest, filename = parts
            results[filename.strip().lstrip("*")] = digest.strip().lower()
    return results


def verify_file_sha256(file_path: Path, expected_sha256: str) -> bool:
    """Verify that a file's SHA-256 matches expected digest using constant-time comparison."""
    p = Path(file_path)
    if not p.is_file():
        return False

    hasher = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)

    computed = hasher.hexdigest().lower()
    return hmac.compare_digest(computed, expected_sha256.lower().strip())


def check_for_updates(
    current_version: str | None = None,
    repo: str = DEFAULT_REPO,
    force: bool = False,
    cache_path: Path | None = None,
    timeout: float = 5.0,
) -> UpdateInfo | None:
    """Check GitHub Releases API for a newer version of Cuttle.

    Returns UpdateInfo if an update is available, or None if up to date or offline.
    """
    curr: str = (
        str(current_version) if current_version else str(getattr(cuttle, "__version__", "1.0.0"))
    )
    cache_file = cache_path or get_default_update_cache_path()

    # 1. Check local cache cooldown unless forced
    now = time.time()
    if not force and cache_file.is_file():
        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
            last_checked = float(cache_data.get("last_checked", 0))
            if now - last_checked < DEFAULT_CHECK_INTERVAL_S:
                cached_update = cache_data.get("update_info")
                if cached_update and is_newer_version(cached_update.get("version", ""), curr):
                    return UpdateInfo(**cached_update)
                return None
        except Exception as exc:
            logger.debug("Failed to read update cache: %s", exc)

    # 2. Query GitHub Releases API
    url = GITHUB_API_URL.format(repo=repo)
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"Cuttle-Worker/{curr}",
    }
    req = urllib.request.Request(url, headers=headers)

    data: dict[str, Any] = {}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.debug("Update check request failed (%s): %s", url, exc)
        return None

    tag_name = data.get("tag_name", "").lstrip("vV")
    if not tag_name or not is_newer_version(tag_name, curr):
        # Update cache to reflect that we are up to date
        _write_cache(cache_file, now, None)
        return None

    # Parse download asset URLs
    installer_url = None
    portable_url = None
    checksums_url = None

    for asset in data.get("assets", []):
        name = asset.get("name", "").lower()
        download_url = asset.get("browser_download_url")
        if "setup" in name and name.endswith(".exe"):
            installer_url = download_url
        elif "portable" in name and name.endswith(".zip"):
            portable_url = download_url
        elif "sha256sums" in name:
            checksums_url = download_url

    info = UpdateInfo(
        version=tag_name,
        release_notes=data.get("body", "") or "",
        html_url=data.get("html_url", f"https://github.com/{repo}/releases/latest"),
        installer_url=installer_url,
        portable_url=portable_url,
        checksums_url=checksums_url,
        published_at=data.get("published_at", ""),
    )

    # Cache successful check
    _write_cache(cache_file, now, info)
    return info


def _write_cache(cache_file: Path, timestamp: float, info: UpdateInfo | None) -> None:
    """Save update check timestamp and details to cache file."""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_checked": timestamp,
            "update_info": asdict(info) if info else None,
        }
        cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("Failed to write update cache: %s", exc)


def dispatch_update_notification(update_info: UpdateInfo) -> bool:
    """Trigger native Windows toast notification announcing update availability."""
    if sys.platform != "win32":
        return False

    try:
        from cuttle.platform.windows.toast import notify_update

        url = (
            update_info.html_url or update_info.installer_url or "https://github.com/Ameya79/cuttle"
        )
        return notify_update(update_info.version, url)
    except Exception as exc:
        logger.warning("Failed to dispatch update notification: %s", exc)
        return False


def start_background_update_check(
    current_version: str | None = None,
    delay_s: float = 3.0,
) -> threading.Thread:
    """Spawn an asynchronous daemon thread to check for updates shortly after startup."""

    def _worker() -> None:
        if delay_s > 0:
            time.sleep(delay_s)
        try:
            info = check_for_updates(current_version=current_version)
            if info:
                logger.info(
                    "Found newer Cuttle version: %s (current: %s)",
                    info.version,
                    current_version,
                )
                dispatch_update_notification(info)
        except Exception as exc:
            logger.debug("Background update check failed: %s", exc)

    thread = threading.Thread(target=_worker, name="CuttleUpdateCheck", daemon=True)
    thread.start()
    return thread
