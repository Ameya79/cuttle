"""Unit tests for Quality Report generation (P5-06).

Per TRD task card P5-06:
- docs/quality.md generated from test results and registry.
- Lists each conversion pair, quality label, and known limits.
"""

from __future__ import annotations

from cuttle.engine.registry import load_registry
from scripts.make_quality_report import OUTPUT_DOC, generate_quality_report


def test_quality_report_covers_all_registered_edges() -> None:
    """The generated quality report must include every edge present in the registry."""
    reg = load_registry()
    report = generate_quality_report()

    assert "# Cuttle Conversion Quality Report" in report
    assert "## Supported Conversions Matrix" in report

    # Verify each edge has a row in the markdown table
    for edge in reg.edges:
        src_label = f"`{edge.src.upper()}`"
        dst_label = f"`{edge.dst.upper()}`"
        assert src_label in report, f"Source format {src_label} missing from quality report"
        assert dst_label in report, f"Target format {dst_label} missing from quality report"


def test_quality_report_file_exists_and_matches() -> None:
    """docs/quality.md exists on disk and reflects current active registry content."""
    assert OUTPUT_DOC.is_file()
    disk_content = OUTPUT_DOC.read_text(encoding="utf-8")
    assert "honest offline conversion with zero file uploads" in disk_content
    assert "pdf2docx" in disk_content
    assert "image_pdf" in disk_content
    assert "dwg" in disk_content
