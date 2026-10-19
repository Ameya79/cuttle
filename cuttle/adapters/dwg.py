"""DWG / CAD engineering drawing conversion adapter (P5-05).

Per TRD task card P5-05:
- Detects ODA File Converter or LibreDWG tools on the machine.
- Never bundles external DWG tools.
- Pipeline: DWG -> DXF -> PDF using LibreOffice Draw.
- Quality is always best_effort.
- If no tool is found, raises E_TOOL_MISSING and points to docs/dwg-addon.md.
"""

from __future__ import annotations

import glob
import os
import shutil
import tempfile
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.pdf import validate_pdf
from cuttle.engine.errors import CuttleError
from cuttle.engine.runner import run_command
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)

WARNING_DWG_BEST_EFFORT = (
    "DWG drawing conversion is best-effort. Layouts, custom fonts, or 3D elements may differ."
)
DOCS_DWG_URL = "https://github.com/Ameya79/cuttle/blob/main/docs/dwg-addon.md"


def detect_libredwg() -> str | None:
    """Locate LibreDWG dwg2dxf executable on PATH or in standard user directories."""
    found = shutil.which("dwg2dxf")
    if found:
        return found

    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "LibreDWG" / "dwg2dxf.exe",
        Path(r"C:\Tools\LibreDWG\dwg2dxf.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)

    return None


def detect_oda() -> str | None:
    """Locate ODA File Converter executable on PATH or in Program Files."""
    found = shutil.which("ODAFileConverter")
    if found:
        return found

    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pattern = os.path.join(program_files, "ODA", "ODAFileConverter*", "ODAFileConverter.exe")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]

    return None


def get_available_dwg_tool() -> tuple[str, str] | None:
    """Return the available DWG conversion utility: ('libredwg', path) or ('oda', path)."""
    libredwg = detect_libredwg()
    if libredwg:
        return ("libredwg", libredwg)

    oda = detect_oda()
    if oda:
        return ("oda", oda)

    return None


def convert_dwg_to_dxf(
    dwg_path: Path,
    out_dxf: Path,
    custom_tool: tuple[str, str] | None = None,
    cancel: CancelToken | None = None,
    on_progress: ProgressCb | None = None,
) -> None:
    """Convert an AutoCAD DWG file to DXF format using the detected tool."""
    tool_info = custom_tool or get_available_dwg_tool()
    if not tool_info:
        raise CuttleError(
            code="E_TOOL_MISSING",
            user_message="DWG conversion requires an add-on (LibreDWG or ODA File Converter).",
            detail=(
                f"No DWG tool detected for '{dwg_path.name}'. "
                f"Install LibreDWG or ODA File Converter. See: {DOCS_DWG_URL}"
            ),
        )

    tool_type, tool_bin = tool_info

    if cancel and cancel.cancelled:
        raise CuttleError(
            code="E_CANCELLED",
            user_message="The conversion was cancelled.",
            detail="Cancelled before DWG conversion started.",
        )

    if on_progress:
        on_progress(10.0, f"Converting DWG to DXF using {tool_type}...")

    if tool_type == "libredwg":
        argv = [tool_bin, "-o", str(out_dxf), str(dwg_path)]
        run_command(argv, timeout_s=120, cancel=cancel)
    elif tool_type == "oda":
        # ODAFileConverter: <in_dir> <out_dir> <version> <type> <recurse> <audit>
        with tempfile.TemporaryDirectory() as td:
            in_dir = Path(td) / "in"
            out_dir = Path(td) / "out"
            in_dir.mkdir()
            out_dir.mkdir()

            tmp_dwg = in_dir / dwg_path.name
            shutil.copyfile(dwg_path, tmp_dwg)

            argv = [
                tool_bin,
                str(in_dir),
                str(out_dir),
                "ACAD2018",
                "DXF",
                "0",
                "1",
            ]
            run_command(argv, timeout_s=120, cancel=cancel)

            produced = out_dir / f"{dwg_path.stem}.dxf"
            if not produced.is_file():
                raise CuttleError(
                    code="E_CONV_FAILED",
                    user_message=(
                        f"ODA File Converter failed to produce DXF from '{dwg_path.name}'."
                    ),
                    detail="Expected DXF file was not found in ODA output folder.",
                )
            shutil.copyfile(produced, out_dxf)


class DwgAdapter(BaseAdapter):
    """Adapter for converting DWG/DXF drawings to PDF and DXF."""

    name = "dwg"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Supported: DWG -> PDF, DWG -> DXF, and DXF -> PDF."""
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if src == "dwg" and dst in ("pdf", "dxf"):
            return Quality.BEST_EFFORT

        if src == "dxf" and dst == "pdf":
            return Quality.BEST_EFFORT

        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct DWG conversion plan."""
        args = ["dwg", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=10.0)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute DWG conversion pipeline."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for DWG conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        dst_fmt = plan.args[2].lower()
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before DWG pipeline started.",
            )

        if src.suffix.lower() == ".dwg":
            if dst_fmt == "dxf":
                convert_dwg_to_dxf(src, tmp_out, cancel=cancel, on_progress=on_progress)
            elif dst_fmt == "pdf":
                with tempfile.TemporaryDirectory() as td:
                    temp_dxf = Path(td) / f"{src.stem}.dxf"
                    convert_dwg_to_dxf(src, temp_dxf, cancel=cancel, on_progress=on_progress)

                    if cancel.cancelled:
                        raise CuttleError(
                            code="E_CANCELLED",
                            user_message="The conversion was cancelled.",
                            detail="Cancelled after DWG to DXF conversion.",
                        )

                    # Step 2: Render intermediate DXF to PDF using LibreOffice Draw
                    on_progress(50.0, "Rendering vector drawing to PDF via LibreOffice Draw...")
                    from cuttle.adapters.libreoffice import LibreOfficeAdapter

                    lo_adapter = LibreOfficeAdapter()
                    lo_plan = lo_adapter.plan(temp_dxf, "pdf", tmp_out, {})
                    lo_adapter.run(lo_plan, on_progress=on_progress, cancel=cancel)
            else:
                raise CuttleError(
                    code="E_UNSUPPORTED",
                    user_message=f"DWG adapter cannot convert to '{dst_fmt}'.",
                    detail="Supported output formats are PDF and DXF.",
                )
        elif src.suffix.lower() == ".dxf":
            if dst_fmt == "pdf":
                on_progress(20.0, "Rendering DXF drawing to PDF via LibreOffice Draw...")
                from cuttle.adapters.libreoffice import LibreOfficeAdapter

                lo_adapter = LibreOfficeAdapter()
                lo_plan = lo_adapter.plan(src, "pdf", tmp_out, {})
                lo_adapter.run(lo_plan, on_progress=on_progress, cancel=cancel)
            else:
                raise CuttleError(
                    code="E_UNSUPPORTED",
                    user_message=f"DXF adapter cannot convert to '{dst_fmt}'.",
                    detail="Supported output format for DXF is PDF.",
                )

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled after DWG pipeline completed.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate generated drawing or PDF output."""
        warnings = [WARNING_DWG_BEST_EFFORT]

        if out.suffix.lower() == ".pdf":
            res = validate_pdf(out)
            if not res.ok:
                return res
            warnings.extend(res.warnings)
            return ValidationResult(ok=True, warnings=warnings)

        if not out.is_file() or out.stat().st_size == 0:
            return ValidationResult(ok=False, reason="Output DXF file is missing or empty.")

        return ValidationResult(ok=True, warnings=warnings)
