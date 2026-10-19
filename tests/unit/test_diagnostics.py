"""Unit tests for the diagnostic collector, path redaction, and issue templates (P6-07).

Per TRD task card P6-07:
- Diagnostic report collector redacts sensitive user paths.
- Captures system details, tool status, and recent logs.
- Issue templates and beta test documentation are complete and valid.
"""

from __future__ import annotations

from pathlib import Path

from cuttle.ui.diagnostics import (
    collect_diagnostic_report,
    get_system_info,
    get_tool_status,
    redact_sensitive_paths,
    sanitize_filename,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_redact_sensitive_paths() -> None:
    """Windows user paths and names must be redacted to protect privacy."""
    sample_win_path = r"C:\Users\AliceSmith\AppData\Local\Temp\secret_contract.pdf"
    redacted_win = redact_sensitive_paths(sample_win_path)
    assert "AliceSmith" not in redacted_win
    assert "<REDACTED_USER>" in redacted_win

    sample_fwd_path = "C:/Users/BobJones/Documents/taxes_2025.xlsx"
    redacted_fwd = redact_sensitive_paths(sample_fwd_path)
    assert "BobJones" not in redacted_fwd
    assert "<REDACTED_USER>" in redacted_fwd

    assert redact_sensitive_paths("") == ""


def test_sanitize_filename() -> None:
    """Filenames must be stripped down to generic file.<ext>."""
    assert sanitize_filename(r"C:\Confidential\Patent_Filing.PDF") == "file.pdf"
    assert sanitize_filename("private_photo.png") == "file.png"
    assert sanitize_filename(None) == "unknown"


def test_system_info_and_tools() -> None:
    """System info and tool checks must return valid dictionaries."""
    info = get_system_info()
    assert "cuttle_version" in info
    assert "platform" in info
    assert "architecture" in info

    tools = get_tool_status()
    assert "ffmpeg" in tools
    assert "pandoc" in tools
    assert "soffice" in tools


def test_collect_diagnostic_report() -> None:
    """Diagnostic report must format Markdown report with redacted information."""
    report = collect_diagnostic_report(
        error_code="E_CONVERT_FAIL",
        error_message=r"Failed to write C:\Users\JohnDoe\output.docx",
        src_path=r"C:\Users\JohnDoe\input.pdf",
        dest_path=r"C:\Users\JohnDoe\output.docx",
        detail="Tool timed out",
    )

    assert "### Cuttle Diagnostic Report" in report
    assert "E_CONVERT_FAIL" in report
    assert "JohnDoe" not in report
    assert "file.pdf" in report
    assert "file.docx" in report
    assert "Recent Logs (Redacted)" in report


def test_issue_templates_and_beta_script_exist() -> None:
    """Verify issue templates and beta test documentation exist and have proper structure."""
    templates_dir = PROJECT_ROOT / ".github" / "ISSUE_TEMPLATE"
    assert (templates_dir / "bug_report.md").is_file()
    assert (templates_dir / "bad_conversion.md").is_file()
    assert (templates_dir / "format_request.md").is_file()

    bug_content = (templates_dir / "bug_report.md").read_text(encoding="utf-8")
    assert "name: Bug Report" in bug_content
    assert "[BUG]" in bug_content

    beta_script = PROJECT_ROOT / "docs" / "beta-test-script.md"
    assert beta_script.is_file()
    beta_content = beta_script.read_text(encoding="utf-8")
    assert "Cuttle Beta Test Script" in beta_content
    assert "Windows 11 Native Integration" in beta_content or "Windows 11" in beta_content
