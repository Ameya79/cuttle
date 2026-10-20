"""Pandoc conversion adapter for Markdown, HTML, Word (DOCX), and Plain Text.

Per TRD §6.1, §6.2, and task card P3-01:
- Always passes -f and -t explicitly.
- Output goes directly to temporary .cuttle-part file.
- Inspects Pandoc binary to append --sandbox when supported.
- Streams indeterminate progress and validates generated documents.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.engine.errors import CuttleError
from cuttle.engine.runner import run_command
from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)

PANDOC_INPUT_FORMAT_MAP: dict[str, str] = {
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
    "htm": "html",
    "docx": "docx",
    "txt": "markdown",
}

PANDOC_OUTPUT_FORMAT_MAP: dict[str, str] = {
    "md": "markdown",
    "markdown": "markdown",
    "html": "html",
    "htm": "html",
    "docx": "docx",
    "txt": "plain",
}


@functools.lru_cache(maxsize=1)
def resolve_pandoc_binary() -> str:
    """Resolve the pandoc executable from vendor/ or system PATH."""
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).parent
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
    vendor_tool = project_root / "vendor" / "pandoc.exe"
    if vendor_tool.is_file():
        return str(vendor_tool)

    sys_bin = shutil.which("pandoc")
    if sys_bin:
        return sys_bin

    raise CuttleError(
        code="E_TOOL_MISSING",
        user_message="Pandoc is required for document conversions but was not found.",
        detail="pandoc.exe not found in vendor/ or PATH. Run 'python scripts/fetch_tools.py'.",
    )


@functools.lru_cache(maxsize=1)
def check_sandbox_supported(pandoc_bin: str) -> bool:
    """Determine whether the installed pandoc supports the --sandbox flag."""
    try:
        res = subprocess.run(
            [pandoc_bin, "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return "--sandbox" in res.stdout
    except Exception:
        return False


class PandocAdapter(BaseAdapter):
    """Adapter for document conversions using Pandoc."""

    name = "pandoc"

    def __init__(self, pandoc_path: str | None = None) -> None:
        self._custom_pandoc = pandoc_path

    @property
    def pandoc(self) -> str:
        """Return the resolved pandoc executable path."""
        if self._custom_pandoc:
            return self._custom_pandoc
        return resolve_pandoc_binary()

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Return quality rating if pandoc can perform conversion, else None."""
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if src not in PANDOC_INPUT_FORMAT_MAP or dst not in PANDOC_OUTPUT_FORMAT_MAP:
            return None
        if src == dst:
            return None

        # DOCX extraction to text/markdown is lossy (styling, margins, headers/footers lost)
        if src == "docx":
            return Quality.LOSSY

        return Quality.LOSSLESS

    def build_argv(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str] | None = None,
    ) -> list[str]:
        """Build exact Pandoc command line arguments with explicit -f and -t."""
        src_clean = src.suffix.lstrip(".").lower()
        # Resolve input and output format identifiers
        src_pandoc_fmt = PANDOC_INPUT_FORMAT_MAP.get(src_clean, "markdown")
        dst_pandoc_fmt = PANDOC_OUTPUT_FORMAT_MAP.get(dst_fmt.lower(), dst_fmt.lower())

        argv = [
            self.pandoc,
            "-f",
            src_pandoc_fmt,
            "-t",
            dst_pandoc_fmt,
        ]

        if check_sandbox_supported(self.pandoc):
            argv.append("--sandbox")

        if dst_fmt.lower() == "html":
            argv.append("-s")

        argv.extend(["-o", str(tmp_out), str(src)])
        return argv

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct conversion plan for Pandoc."""
        argv = self.build_argv(src, dst_fmt, tmp_out, options)
        return Plan(args=argv)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute Pandoc process, reporting indeterminate progress."""
        on_progress(None, "Converting document with Pandoc...")

        run_command(
            plan.args,
            timeout_s=120.0,
            on_stdout_line=None,
            cancel=cancel,
        )

        on_progress(100.0, "Complete")

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate output file integrity."""
        if not out.is_file():
            return ValidationResult(
                ok=False,
                reason="Pandoc output file does not exist.",
            )

        try:
            size = out.stat().st_size
            if size == 0:
                return ValidationResult(
                    ok=False,
                    reason="Pandoc output file is empty (0 bytes).",
                )
        except OSError as exc:
            return ValidationResult(
                ok=False,
                reason=f"Could not inspect output file: {exc}",
            )

        # Check DOCX validity as zip archive with word/document.xml
        stem_lower = out.name.lower()
        if ".docx" in stem_lower:
            try:
                with zipfile.ZipFile(out, "r") as z:
                    names = z.namelist()
                    if not any(n.startswith("word/") for n in names):
                        return ValidationResult(
                            ok=False,
                            reason="Output DOCX missing required word/ components.",
                        )
            except Exception as exc:
                return ValidationResult(
                    ok=False,
                    reason=f"Output is not a valid DOCX zip archive: {exc}",
                )

        return ValidationResult(ok=True)
