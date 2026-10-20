"""PDF to Word (DOCX) conversion adapter using pdf2docx with high-fidelity layout preservation.

Per TRD task card P5-02 & document layout fidelity invariants:
- Preserves exact geometry, text flow, and stream/lattice tables.
- Eliminates artificial line wrapping and excessive paragraph after-spacing.
- Text PDF converts to a DOCX that opens cleanly and matches original page counts.
- Scanned PDF without OCR raises E_UNSUPPORTED with a message offering OCR.
"""

from __future__ import annotations

import logging
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.pdf import is_scanned_pdf
from cuttle.engine.errors import CuttleError
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)
from cuttle.engine.validators import validate_office_document

logger = logging.getLogger(__name__)

WARNING_TOUCH_UPS = "Tables and complex layouts may need touch ups."

# XML namespace for WordprocessingML
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def probe_pdf_layout_geometry(src: Path) -> dict[str, float]:
    """Inspect PDF page geometry to determine safe margin factors."""
    try:
        import fitz

        doc = fitz.open(src)
        try:
            if len(doc) == 0:
                return {}
            page = doc[0]
            rect = page.rect
            blocks = page.get_text("blocks")
            if not blocks:
                return {"width": float(rect.width), "height": float(rect.height)}

            min_y0 = min(b[1] for b in blocks)
            max_y1 = max(b[3] for b in blocks)
            margin_top = max(0.0, float(min_y0))
            margin_bottom = max(0.0, float(rect.height - max_y1))

            return {
                "width": float(rect.width),
                "height": float(rect.height),
                "margin_top": margin_top,
                "margin_bottom": margin_bottom,
            }
        finally:
            doc.close()
    except Exception as exc:
        logger.debug("Could not probe PDF geometry for %s: %s", src.name, exc)
        return {}


def normalize_docx_layout(docx_path: Path) -> None:
    """Normalize paragraph spacing in OpenXML to eliminate artificial page bloat."""
    try:
        ET.register_namespace("w", _W_NS)
        ns = {"w": _W_NS}

        with tempfile.TemporaryDirectory(prefix="cuttle_docx_norm_") as td:
            tmp_unzip = Path(td) / "unzipped"
            with zipfile.ZipFile(docx_path, "r") as zf:
                zf.extractall(tmp_unzip)

            doc_xml = tmp_unzip / "word" / "document.xml"
            if not doc_xml.is_file():
                return

            tree = ET.parse(doc_xml)
            root = tree.getroot()

            # Inspect paragraphs and adjust after-spacing
            paras = root.findall(".//w:p", ns)
            modified = False
            for p in paras:
                p_pr = p.find("w:pPr", ns)
                if p_pr is not None:
                    spacing = p_pr.find("w:spacing", ns)
                    if spacing is not None:
                        after_key = f"{{{_W_NS}}}after"
                        after_val = spacing.get(after_key)
                        if after_val is not None:
                            try:
                                # If after spacing exceeds standard running line spacing (160 dxa),
                                # cap it to avoid pushing lines onto additional trailing pages
                                val_int = int(after_val)
                                if val_int > 160:
                                    spacing.set(after_key, "80")
                                    modified = True
                            except ValueError:
                                pass

            if modified:
                tree.write(doc_xml, xml_declaration=True, encoding="utf-8")
                tmp_zip = Path(td) / "repacked.docx"
                with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf_out:
                    for file_path in tmp_unzip.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(tmp_unzip)
                            zf_out.write(file_path, arcname)
                tmp_zip.replace(docx_path)
    except Exception as exc:
        logger.warning("Could not normalize DOCX layout for %s: %s", docx_path.name, exc)


class Pdf2DocxAdapter(BaseAdapter):
    """Adapter for converting searchable PDF documents to Microsoft Word (DOCX)."""

    name = "pdf2docx"

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """PDF to Word conversion is supported with best_effort quality."""
        if src_fmt.lower() == "pdf" and dst_fmt.lower() == "docx":
            return Quality.BEST_EFFORT
        return None

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for PDF to DOCX."""
        if dst_fmt.lower() != "docx":
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=f"pdf2docx adapter cannot convert to '{dst_fmt}'.",
                detail="Only .docx output is supported by pdf2docx.",
            )

        password = options.get("password")
        if is_scanned_pdf(src, password=password):
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message=(
                    "This PDF appears to be a scanned document without text. "
                    "Run OCR before converting to Word."
                ),
                detail=(
                    f"Scanned PDF detected in '{src.name}'. "
                    "Run OCR first to recognize text before Word conversion."
                ),
            )

        args = ["pdf2docx", str(src), dst_fmt.lower(), str(tmp_out)]
        return Plan(args=args, duration_s=None)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute PDF to Word conversion using pdf2docx with high-fidelity layout parameters."""
        if len(plan.args) < 4:
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="Invalid plan arguments for PDF to Word conversion.",
                detail=f"Expected 4 arguments in plan.args, got {plan.args}",
            )

        src = Path(plan.args[1])
        tmp_out = Path(plan.args[3])

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled before starting PDF to Word conversion.",
            )

        try:
            from pdf2docx import Converter
        except ImportError as exc:
            raise CuttleError(
                code="E_TOOL_MISSING",
                user_message="The pdf2docx library is required for PDF to Word conversion.",
                detail=str(exc),
            ) from exc

        on_progress(10.0, "Parsing PDF pages and geometry...")

        # Probe layout geometry to prevent premature page-breaks
        geometry = probe_pdf_layout_geometry(src)
        margin_bottom = geometry.get("margin_bottom", 50.0)
        margin_top = geometry.get("margin_top", 50.0)

        # Tune margin factors based on actual document geometry
        factor_top = 0.1 if margin_top < 40.0 else 0.3
        factor_bottom = 0.1 if margin_bottom < 40.0 else 0.3

        try:
            cv = Converter(str(src))
            try:
                on_progress(30.0, "Converting layout and content...")
                if cancel.cancelled:
                    raise CuttleError(
                        code="E_CANCELLED",
                        user_message="The conversion was cancelled.",
                        detail="Cancelled during PDF to Word conversion.",
                    )

                # High-fidelity layout preservation settings:
                # - line_break_width_ratio=0.08: avoids false paragraph breaks
                # - line_overlap_threshold=0.85: keeps running words on same line
                # - new_paragraph_free_space_ratio=0.92: keeps paragraphs intact
                # - extract_stream_table=True: converts borderless tabular data to Word tables
                # - parse_lattice_table=True & parse_stream_table=True: parses both table kinds
                # - delete_end_line_hyphen=True: rejoins hyphenated words cleanly
                cv.convert(
                    str(tmp_out),
                    line_break_width_ratio=0.08,
                    line_overlap_threshold=0.85,
                    new_paragraph_free_space_ratio=0.92,
                    extract_stream_table=True,
                    parse_lattice_table=True,
                    parse_stream_table=True,
                    delete_end_line_hyphen=True,
                    page_margin_factor_top=factor_top,
                    page_margin_factor_bottom=factor_bottom,
                )

                on_progress(85.0, "Normalizing document spacing...")
                normalize_docx_layout(tmp_out)

                on_progress(95.0, "Finalizing Word document...")
            finally:
                cv.close()
        except Exception as exc:
            if isinstance(exc, CuttleError):
                raise
            raise CuttleError(
                code="E_CONV_FAILED",
                user_message=f"Failed to convert '{src.name}' to Word.",
                detail=str(exc),
            ) from exc

        if cancel.cancelled:
            raise CuttleError(
                code="E_CANCELLED",
                user_message="The conversion was cancelled.",
                detail="Cancelled after DOCX generation.",
            )

        on_progress(100.0, "Done")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate that the generated DOCX is a well-formed Word document."""
        res = validate_office_document(out, expected_fmt="docx")
        if not res.ok:
            return res

        warnings = list(res.warnings)
        warnings.append(WARNING_TOUCH_UPS)
        return ValidationResult(ok=True, warnings=warnings)
