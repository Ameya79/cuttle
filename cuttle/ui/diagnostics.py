"""Diagnostic report collector and path redaction utilities (P6-07).

Per TRD task card P6-07:
- Formats diagnostic reports for 'Copy Details' on conversion errors.
- Strips sensitive user paths, directory names, and personally identifiable info.
- Gathers system info, doctor status, and recent worker log lines.
- Safe for public pasting into GitHub issues.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import sys
from pathlib import Path

import cuttle

logger = logging.getLogger(__name__)


def redact_sensitive_paths(text: str) -> str:
    """Redact Windows user paths and usernames to prevent leaking private information."""
    if not text:
        return ""

    redacted = text

    # Redact actual current username if present in environment
    username = os.environ.get("USERNAME")
    if username and len(username) > 2:
        redacted = re.sub(re.escape(username), "<REDACTED_USER>", redacted, flags=re.IGNORECASE)

    # Redact standard Windows user paths: C:\Users\<name>\... or C:/Users/<name>/...
    redacted = re.sub(
        r"([A-Za-z]:\\[Uu]sers\\)[^\s\\\"\'\<\>]+",
        r"\1<REDACTED_USER>",
        redacted,
    )
    redacted = re.sub(
        r"([A-Za-z]:/[Uu]sers/)[^\s/\"\'\<\>]+",
        r"\1<REDACTED_USER>",
        redacted,
    )

    # Redact temporary paths
    temp_dir = os.environ.get("TEMP")
    if temp_dir:
        redacted = re.sub(re.escape(temp_dir), "<TEMP_DIR>", redacted, flags=re.IGNORECASE)

    return redacted


def sanitize_filename(filepath: str | Path | None) -> str:
    """Extract format extension and redact private filename."""
    if not filepath:
        return "unknown"
    p = Path(filepath)
    ext = p.suffix.lower()
    return f"file{ext}" if ext else "file"


def get_system_info() -> dict[str, str]:
    """Gather non-sensitive system environment metrics."""
    return {
        "cuttle_version": getattr(cuttle, "__version__", "1.0.0"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu_count": str(os.cpu_count() or 1),
    }


def get_tool_status() -> dict[str, str]:
    """Check availability of external conversion tools."""
    tools = ["ffmpeg", "pandoc", "soffice", "tesseract", "dwg2dxf"]
    status: dict[str, str] = {}
    import shutil

    for tool in tools:
        found = shutil.which(tool)
        status[tool] = "installed" if found else "not found"
    return status


def get_recent_worker_logs(max_lines: int = 50) -> list[str]:
    """Retrieve last N lines from worker.log with sensitive user paths redacted."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    log_file = base / "Cuttle" / "worker.log"

    if not log_file.is_file():
        return ["[No worker.log found in local app data]"]

    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        tail = lines[-max_lines:] if len(lines) > max_lines else lines
        return [redact_sensitive_paths(line) for line in tail]
    except Exception as exc:
        logger.debug("Failed reading worker.log: %s", exc)
        return [f"[Error reading worker.log: {exc}]"]


def collect_diagnostic_report(
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    src_path: str | Path | None = None,
    dest_path: str | Path | None = None,
    detail: str | None = None,
    max_log_lines: int = 40,
) -> str:
    """Generate a clean, privacy-redacted diagnostic report ready for GitHub issues."""
    sys_info = get_system_info()
    tools = get_tool_status()
    logs = get_recent_worker_logs(max_lines=max_log_lines)

    lines: list[str] = [
        "### Cuttle Diagnostic Report",
        "",
        "#### Conversion Error Details",
        f"- **Error Code**: `{error_code or 'UNKNOWN'}`",
        f"- **Message**: {redact_sensitive_paths(error_message or 'No message provided')}",
        f"- **Source**: `{sanitize_filename(src_path)}`",
        f"- **Target**: `{sanitize_filename(dest_path)}`",
    ]

    if detail:
        lines.extend(
            [
                f"- **Detail**: {redact_sensitive_paths(detail)}",
            ]
        )

    lines.extend(
        [
            "",
            "#### Environment",
            f"- **Cuttle**: v{sys_info['cuttle_version']}",
            f"- **OS**: {sys_info['platform']} ({sys_info['architecture']})",
            f"- **Python**: {sys_info['python_version']}",
            f"- **CPUs**: {sys_info['cpu_count']}",
            "",
            "#### Tools Status",
        ]
    )

    for tool_name, tool_st in sorted(tools.items()):
        lines.append(f"- **{tool_name}**: `{tool_st}`")

    lines.extend(
        [
            "",
            "#### Recent Logs (Redacted)",
            "```text",
        ]
    )
    lines.extend(logs)
    lines.extend(
        [
            "```",
            "",
            "*(All personal user folder paths have been automatically redacted)*",
        ]
    )

    return "\n".join(lines)


def copy_diagnostic_report_to_clipboard(
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    src_path: str | Path | None = None,
    dest_path: str | Path | None = None,
    detail: str | None = None,
) -> bool:
    """Generate diagnostic report and copy directly to Windows clipboard."""
    report = collect_diagnostic_report(
        error_code=error_code,
        error_message=error_message,
        src_path=src_path,
        dest_path=dest_path,
        detail=detail,
    )
    try:
        from cuttle.platform.windows.toast import copy_to_clipboard

        return copy_to_clipboard(report)
    except Exception as exc:
        logger.warning("Failed copying diagnostic report to clipboard: %s", exc)
        return False
