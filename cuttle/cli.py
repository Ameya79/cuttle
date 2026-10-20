"""Cuttle CLI — command-line interface for conversion engine.

Per TRD §6.6:
- convert <src> --to <fmt> [--out <dir>] [--json]
- targets <src> [--json]
- formats [--json]
- doctor [--json]

Exit codes:
- 0: Success.
- 1: User or conversion error (CuttleError).
- 2: Invalid command line arguments (handled by Typer).
- 3: Fatal unexpected crash.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import filetype
import pillow_heif
import psutil
import pypdf
import typer
from PIL import Image

from cuttle.engine.convert import convert as engine_convert
from cuttle.engine.convert import list_targets
from cuttle.engine.errors import CuttleError
from cuttle.engine.registry import load_registry

app = typer.Typer(
    name="cuttle",
    help="Right-click file converter. Convert files offline from the command line.",
    no_args_is_help=True,
    add_completion=False,
)


def _resolve_binary_info(tool_name: str) -> dict[str, object]:
    """Check binary location and version."""
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).parent
    else:
        project_root = Path(__file__).resolve().parent.parent
    vendor_tool = project_root / "vendor" / f"{tool_name}.exe"

    target_bin: str | None = None
    if vendor_tool.is_file():
        target_bin = str(vendor_tool)
    else:
        system_bin = shutil.which(tool_name)
        if system_bin:
            target_bin = system_bin

    if not target_bin:
        return {"installed": False, "path": None, "version": None}

    version_str: str | None = None
    try:
        flag = "-version" if tool_name.startswith("ff") else "--version"
        res = subprocess.run(
            [target_bin, flag],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout:
            version_str = res.stdout.splitlines()[0].strip()
    except Exception:
        version_str = "available"

    return {"installed": True, "path": target_bin, "version": version_str}


@app.command(name="convert")
def convert_command(
    src: Path = typer.Argument(..., help="Path to the file or directory to convert."),
    to: str = typer.Option(..., "--to", "-t", help="Target format ID (e.g. mp3, jpg, webm)."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Output directory."),
    json_mode: bool = typer.Option(
        False, "--json", help="Emit NDJSON stream instead of formatted text."
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        "-r/-R",
        help="Recursively convert files if src is a directory.",
    ),
    filter_ext: str | None = typer.Option(
        None,
        "--filter",
        help="Comma-separated extensions to include when converting a directory.",
    ),
) -> None:
    """Convert a file or an entire directory to the target format."""
    if src.is_dir():
        from cuttle.engine.folder import convert_folder

        ext_set = [e.strip() for e in filter_ext.split(",")] if filter_ext else None
        f_res = convert_folder(src, to, out_dir=out, recursive=recursive, ext_filter=ext_set)
        if json_mode:
            payload = {
                "type": "folder_summary",
                "total": f_res.total_files,
                "succeeded": f_res.succeeded,
                "failed": f_res.failed,
                "skipped": f_res.skipped,
            }
            typer.echo(json.dumps(payload))
        else:
            typer.echo(
                f"Folder conversion complete: {f_res.succeeded} succeeded, "
                f"{f_res.failed} failed, {f_res.skipped} skipped out of {f_res.total_files} files."
            )
        raise typer.Exit(code=0 if f_res.failed == 0 else 1)

    def on_progress(pct: float | None, msg: str = "") -> None:
        if json_mode:
            payload = {"type": "progress", "percent": pct, "message": msg}
            typer.echo(json.dumps(payload))
        elif pct is not None:
            # Human readable progress
            typer.echo(f"Converting: {pct:.1f}% ({msg})", err=True)

    try:
        result = engine_convert(
            src=src,
            dst_fmt=to,
            out_dir=out,
            on_progress=on_progress,
        )

        if json_mode:
            success_payload = {
                "type": "success",
                "output": str(result.output),
                "quality": result.quality.value,
                "warnings": result.warnings,
            }
            typer.echo(json.dumps(success_payload))
        else:
            for warning in result.warnings:
                typer.echo(f"Warning: {warning}", err=True)
            typer.echo(f"Converted: {result.output} [{result.quality.value}]")

        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except CuttleError as err:
        if json_mode:
            err_payload = {
                "type": "error",
                "code": err.code,
                "message": err.user_message,
                "detail": err.detail,
            }
            typer.echo(json.dumps(err_payload))
        else:
            typer.echo(f"Error [{err.code}]: {err.user_message}", err=True)
            if err.detail:
                typer.echo(f"Detail: {err.detail}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as err:
        if json_mode:
            fatal_payload = {
                "type": "fatal",
                "code": "E_INTERNAL",
                "message": "An unexpected error occurred.",
                "detail": str(err),
            }
            typer.echo(json.dumps(fatal_payload))
        else:
            typer.echo(f"Fatal crash: {err}", err=True)
        raise typer.Exit(code=3) from None


@app.command(name="targets")
def targets_command(
    src: Path = typer.Argument(..., help="Path to source file."),
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List reachable conversion targets for a given source file."""
    try:
        target_list = list_targets(src)

        if json_mode:
            data = [
                {
                    "fmt": t.fmt,
                    "label": t.label,
                    "quality": t.quality.value,
                    "available": t.available,
                    "missing": t.missing,
                }
                for t in target_list
            ]
            typer.echo(json.dumps(data))
        else:
            typer.echo(f"Available conversion targets for {src.name}:")
            for t in target_list:
                status = "available" if t.available else f"missing tool: {t.missing}"
                typer.echo(f"  {t.fmt:8} {t.label:24} [{t.quality.value:10}] ({status})")

        raise typer.Exit(code=0)

    except typer.Exit:
        raise
    except CuttleError as err:
        if json_mode:
            typer.echo(
                json.dumps(
                    {
                        "type": "error",
                        "code": err.code,
                        "message": err.user_message,
                        "detail": err.detail,
                    }
                )
            )
        else:
            typer.echo(f"Error [{err.code}]: {err.user_message}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as err:
        typer.echo(f"Fatal crash: {err}", err=True)
        raise typer.Exit(code=3) from None


@app.command(name="formats")
def formats_command(
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List all supported formats in the registry."""
    reg = load_registry()

    if json_mode:
        data = {
            fmt_id: {"kind": f.kind, "extensions": f.ext, "magic": f.magic}
            for fmt_id, f in reg.formats.items()
        }
        typer.echo(json.dumps(data))
    else:
        typer.echo("Registered formats:")
        for fmt_id, f in sorted(reg.formats.items()):
            exts = ", ".join(f.ext)
            typer.echo(f"  {fmt_id:8} [{f.kind:10}] extensions: {exts}")

    raise typer.Exit(code=0)


@app.command(name="install-shell")
def install_shell_command() -> None:
    """Register File Explorer context menus for all supported formats."""
    from cuttle.shell.registry_installer import install_context_menus

    keys = install_context_menus()
    typer.echo(f"Registered {len(keys)} context menu keys.")
    raise typer.Exit(code=0)


@app.command(name="uninstall-shell")
def uninstall_shell_command() -> None:
    """Unregister File Explorer context menus."""
    from cuttle.shell.registry_installer import uninstall_context_menus

    count = uninstall_context_menus()
    typer.echo(f"Uninstalled {count} context menu keys.")
    raise typer.Exit(code=0)


@app.command(name="doctor")
def doctor_command(
    json_mode: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Inspect environment, bundled tools, and library status."""
    tools = {
        "ffmpeg": _resolve_binary_info("ffmpeg"),
        "ffprobe": _resolve_binary_info("ffprobe"),
        "pandoc": _resolve_binary_info("pandoc"),
    }

    # Optional add-on tools
    from cuttle.adapters.dwg import detect_libredwg, detect_oda
    from cuttle.adapters.ocr import detect_ocrmypdf, detect_tesseract
    from cuttle.platform.windows.office_detect import detect_office

    office_info = detect_office()
    tesseract_path = detect_tesseract()
    ocrmypdf_path = detect_ocrmypdf()
    libredwg_path = detect_libredwg()
    oda_path = detect_oda()

    optional_tools: dict[str, dict[str, object]] = {
        "libreoffice": {
            "installed": office_info.installed,
            "path": str(office_info.path) if office_info.path else None,
            "version": office_info.version or ("Available" if office_info.installed else None),
        },
        "tesseract": {
            "installed": bool(tesseract_path),
            "path": str(tesseract_path) if tesseract_path else None,
            "version": "Available" if tesseract_path else None,
        },
        "ocrmypdf": {
            "installed": bool(ocrmypdf_path),
            "path": str(ocrmypdf_path) if ocrmypdf_path else None,
            "version": "Available" if ocrmypdf_path else None,
        },
        "dwg2dxf": {
            "installed": bool(libredwg_path),
            "path": str(libredwg_path) if libredwg_path else None,
            "version": "Available" if libredwg_path else None,
        },
        "oda_converter": {
            "installed": bool(oda_path),
            "path": str(oda_path) if oda_path else None,
            "version": "Available" if oda_path else None,
        },
    }

    try:
        import pdf2docx

        pdf2docx_ver = getattr(pdf2docx, "__version__", "installed")
    except ImportError:
        pdf2docx_ver = "not installed"

    libraries = {
        "Pillow": {"version": getattr(Image, "__version__", "unknown")},
        "pillow-heif": {"version": getattr(pillow_heif, "__version__", "unknown")},
        "filetype": {"version": getattr(filetype, "__version__", "unknown")},
        "psutil": {"version": getattr(psutil, "__version__", "unknown")},
        "pypdf": {"version": getattr(pypdf, "__version__", "unknown")},
        "pdf2docx": {"version": pdf2docx_ver},
    }

    # Core required tools for Phase 1 are ffmpeg and ffprobe
    phase1_ok = bool(tools["ffmpeg"]["installed"] and tools["ffprobe"]["installed"])
    core_ready = bool(phase1_ok and tools["pandoc"]["installed"])

    if json_mode:
        payload = {
            "status": "ok" if phase1_ok else "incomplete",
            "phase": 1,
            "release": "1.0.0",
            "core_ready": core_ready,
            "tools": tools,
            "optional_tools": optional_tools,
            "libraries": libraries,
        }
        typer.echo(json.dumps(payload))
    else:
        typer.echo("Cuttle Doctor — System Status:")
        typer.echo("--- Core Bundled Tools ---")
        for name, info in tools.items():
            if info["installed"]:
                typer.echo(f"  [OK]      {name:10} {info['path']} ({info['version']})")
            else:
                opt_str = " (optional for Phase 1)" if name == "pandoc" else " (REQUIRED)"
                typer.echo(f"  [MISSING] {name:10}{opt_str}")

        typer.echo("--- Optional Add-On Tools ---")
        for name, info in optional_tools.items():
            if info["installed"]:
                typer.echo(f"  [OK]      {name:12} {info['path']}")
            else:
                typer.echo(f"  [OPTIONAL] {name:12} (not installed; add-on feature)")

        typer.echo("--- Python Libraries ---")
        for lib, l_info in libraries.items():
            typer.echo(f"  [OK]      {lib:12} version {l_info['version']}")

        if core_ready:
            typer.echo("\nPhase 1 status: READY (all required tools and libraries available)")
            typer.echo("v1.0.0 Release Status: READY (all core conversion tools available)")
        elif phase1_ok:
            typer.echo("\nPhase 1 status: READY (all required tools and libraries available)")
        else:
            typer.echo("\nPhase 1 status: INCOMPLETE (missing required tools)", err=True)

    raise typer.Exit(code=0 if phase1_ok else 1)


if __name__ == "__main__":
    app()
