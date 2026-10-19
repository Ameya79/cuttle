"""Unit tests for DWG add-on adapter and pipeline (P5-05).

Per TRD task card P5-05:
- Detects ODA File Converter or LibreDWG tools on the machine.
- Never bundles them.
- Pipeline: DWG to DXF, then to PDF via LibreOffice Draw.
- Quality is always best_effort.
- If no tool is found, shows '(needs DWG add-on)' and links to docs/dwg-addon.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pypdf
import pytest

from cuttle.adapters.dwg import (
    DOCS_DWG_URL,
    WARNING_DWG_BEST_EFFORT,
    DwgAdapter,
    convert_dwg_to_dxf,
    detect_libredwg,
    detect_oda,
    get_available_dwg_tool,
)
from cuttle.engine.convert import list_targets
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken, Quality


def create_synthetic_dwg(path: Path) -> Path:
    """Create a minimal synthetic DWG file starting with AC10 magic bytes."""
    # AC1027 is AutoCAD 2013 DWG header
    header = b"AC1027\x00\x00\x00\x00\x00\x00" + b"\x00" * 100
    path.write_bytes(header)
    return path


def create_synthetic_dxf(path: Path) -> Path:
    """Create a minimal valid ASCII DXF file."""
    content = (
        "0\nSECTION\n2\nHEADER\n0\nENDSEC\n"
        "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0.0\n20\n0.0\n11\n10.0\n21\n10.0\n0\nENDSEC\n"
        "0\nEOF\n"
    )
    path.write_text(content, encoding="ascii")
    return path


def test_tool_detection_defaults() -> None:
    """Tool detection returns str or None without uncaught exceptions."""
    libredwg = detect_libredwg()
    assert libredwg is None or isinstance(libredwg, str)

    oda = detect_oda()
    assert oda is None or isinstance(oda, str)

    avail = get_available_dwg_tool()
    assert avail is None or isinstance(avail, tuple)


def test_missing_dwg_tool_raises_e_tool_missing_with_docs_link(tmp_path: Path) -> None:
    """When DWG tools are missing, conversion raises E_TOOL_MISSING pointing to docs."""
    dwg_file = create_synthetic_dwg(tmp_path / "plan.dwg")
    out_dxf = tmp_path / "plan.dxf"

    with patch("cuttle.adapters.dwg.get_available_dwg_tool", return_value=None):
        with pytest.raises(CuttleError) as exc_info:
            convert_dwg_to_dxf(dwg_file, out_dxf)

        err = exc_info.value
        assert err.code == "E_TOOL_MISSING"
        assert "DWG conversion requires an add-on" in err.user_message
        assert "docs/dwg-addon.md" in err.detail or DOCS_DWG_URL in err.detail


def test_dwg_adapter_capabilities() -> None:
    """DwgAdapter supports DWG -> PDF, DWG -> DXF, and DXF -> PDF at best_effort quality."""
    adapter = DwgAdapter()
    assert adapter.can_convert("dwg", "pdf") == Quality.BEST_EFFORT
    assert adapter.can_convert("dwg", "dxf") == Quality.BEST_EFFORT
    assert adapter.can_convert("dxf", "pdf") == Quality.BEST_EFFORT
    assert adapter.can_convert("dwg", "mp4") is None


def test_dwg_pipeline_execution(tmp_path: Path) -> None:
    """DWG -> DXF -> PDF pipeline produces valid PDF with best_effort warning."""
    dwg_file = create_synthetic_dwg(tmp_path / "blueprint.dwg")
    out_pdf = tmp_path / "blueprint.pdf"
    adapter = DwgAdapter()

    plan = adapter.plan(dwg_file, "pdf", out_pdf, {})
    assert plan.args == ["dwg", str(dwg_file), "pdf", str(out_pdf)]

    def mock_convert_dwg_to_dxf(src: Path, out_dxf: Path, **kwargs: object) -> None:
        create_synthetic_dxf(out_dxf)

    def mock_lo_run(plan_obj: object, on_progress: object, cancel: object) -> None:
        # Simulate LibreOffice Draw outputting a valid PDF
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=400, height=300)
        with open(out_pdf, "wb") as f:
            writer.write(f)

    with (
        patch("cuttle.adapters.dwg.convert_dwg_to_dxf", side_effect=mock_convert_dwg_to_dxf),
        patch("cuttle.adapters.libreoffice.LibreOfficeAdapter.run", side_effect=mock_lo_run),
    ):
        cancel = CancelToken()
        adapter.run(plan, on_progress=lambda p, m: None, cancel=cancel)

    assert out_pdf.is_file()
    assert out_pdf.stat().st_size > 0

    val_res = adapter.validate(dwg_file, out_pdf)
    assert val_res.ok is True
    assert WARNING_DWG_BEST_EFFORT in val_res.warnings


def test_dwg_addon_documentation_exists() -> None:
    """The documentation file docs/dwg-addon.md must exist and describe add-ons."""
    project_root = Path(__file__).resolve().parent.parent.parent
    doc_path = project_root / "docs" / "dwg-addon.md"
    assert doc_path.is_file()
    content = doc_path.read_text(encoding="utf-8")
    assert "LibreDWG" in content
    assert "ODA File Converter" in content
    assert "LibreOffice Draw" in content


def test_list_targets_labels_missing_dwg_addon(tmp_path: Path) -> None:
    """Listing targets for a DWG file without tools flags missing='dwg_addon'."""
    dwg_file = create_synthetic_dwg(tmp_path / "drawing.dwg")

    with patch("cuttle.engine.convert.is_tool_available", side_effect=lambda t: t != "dwg_addon"):
        targets = list_targets(dwg_file)

    pdf_target = next((t for t in targets if t.fmt == "pdf"), None)
    assert pdf_target is not None
    assert pdf_target.available is False
    assert pdf_target.missing == "dwg_addon"
