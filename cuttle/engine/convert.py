"""Core conversion engine wiring.

Implements TRD §6.5 steps 1 through 9:
1. Validate source file existence and lock status (E_SRC_MISSING, E_SRC_LOCKED).
2. Detect format with magic-bytes priority (detect_format).
3. Find optimal conversion path in registry graph (direct or 2-hop).
4. Verify destination directory and disk space (check_free_space).
5. Check external tool requirements (E_TOOL_MISSING).
6. Execute conversion using appropriate adapter (FFmpegAdapter, ImageAdapter).
7. Validate converted output (E_VALIDATION).
8. Safely commit final file with collision avoidance without overwriting.
9. Return ConvertResult with output path, quality badge, and warnings.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from cuttle.adapters.base import BaseAdapter
from cuttle.adapters.ffmpeg import FFmpegAdapter
from cuttle.adapters.image import ImageAdapter
from cuttle.engine.detect import detect_format
from cuttle.engine.errors import CuttleError
from cuttle.engine.graph import ConversionGraph
from cuttle.engine.registry import Registry, load_registry
from cuttle.engine.safe_output import check_free_space, commit_output, temp_output
from cuttle.engine.types import (
    CancelToken,
    ConvertResult,
    Edge,
    ProgressCb,
    Target,
)


def is_tool_available(tool_name: str) -> bool:
    """Check whether a CLI tool binary exists in vendor/ or system PATH."""
    project_root = Path(__file__).resolve().parent.parent.parent
    vendor_tool = project_root / "vendor" / f"{tool_name}.exe"
    if vendor_tool.is_file():
        return True
    return shutil.which(tool_name) is not None


def get_available_tools() -> set[str]:
    """Return set of external tool names currently available."""
    known = ["ffmpeg", "ffprobe", "pandoc", "libreoffice"]
    return {t for t in known if is_tool_available(t)}


def check_source_readable(src: Path) -> None:
    """Verify source file exists, is a regular file, and is not locked by another process."""
    if not src.is_file():
        raise CuttleError(
            code="E_SRC_MISSING",
            user_message=f"Source file not found: {src.name}",
            detail=f"Path does not exist or is not a file: {src}",
        )

    try:
        with open(src, "rb") as f:
            f.read(1)
    except PermissionError as err:
        raise CuttleError(
            code="E_SRC_LOCKED",
            user_message=f"The file '{src.name}' is currently in use or locked by another program.",
            detail=str(err),
        ) from err
    except OSError as err:
        if getattr(err, "winerror", None) in (32, 33):
            raise CuttleError(
                code="E_SRC_LOCKED",
                user_message=f"The file '{src.name}' is locked by another program.",
                detail=str(err),
            ) from err
        raise


def get_adapter(adapter_name: str) -> BaseAdapter:
    """Resolve adapter name to its concrete adapter instance."""
    if adapter_name == "ffmpeg":
        return FFmpegAdapter()
    if adapter_name == "image":
        return ImageAdapter()

    raise CuttleError(
        code="E_TOOL_MISSING",
        user_message=f"Adapter '{adapter_name}' is not recognized.",
        detail=f"No adapter implementation available for '{adapter_name}'.",
    )


def list_targets(
    src: Path,
    registry: Registry | None = None,
) -> list[Target]:
    """List all reachable conversion targets for a given source file."""
    check_source_readable(src)
    reg = registry or load_registry()
    graph = ConversionGraph(reg)
    detected = detect_format(src, registry=reg)

    available_tools = get_available_tools()
    return graph.list_targets(str(detected), available_tools=available_tools)


def _run_single_edge(
    edge: Edge,
    src: Path,
    tmp_out: Path,
    on_progress: ProgressCb,
    cancel: CancelToken,
) -> None:
    """Execute a single conversion edge using its registered adapter and validate."""
    adapter = get_adapter(edge.adapter)
    plan = adapter.plan(src, edge.dst, tmp_out, edge.options)
    adapter.run(plan, on_progress, cancel)

    v_res = adapter.validate(src, tmp_out)
    if not v_res.ok:
        raise CuttleError(
            code="E_VALIDATION",
            user_message=f"Output validation failed: {v_res.reason}",
            detail=v_res.reason,
        )


def _noop_progress(pct: float | None, msg: str = "") -> None:
    pass


def convert(
    src: Path,
    dst_fmt: str,
    *,
    out_dir: Path | None = None,
    on_progress: ProgressCb | None = None,
    cancel: CancelToken | None = None,
    registry: Registry | None = None,
) -> ConvertResult:
    """Convert source file to dst_fmt following TRD §6.5 pipeline."""
    target_fmt = dst_fmt.lower().lstrip(".")
    cancel_token = cancel or CancelToken()
    prog_cb: ProgressCb = on_progress if on_progress is not None else _noop_progress

    # 1. Source verification & lock check
    check_source_readable(src)

    # 2. Registry & format detection
    reg = registry or load_registry()
    graph = ConversionGraph(reg)
    detected = detect_format(src, registry=reg)
    warnings: list[str] = list(detected.warnings)

    # 3. Destination directory & disk space check (2x source size per TRD §6.5)
    dest_dir = out_dir if out_dir is not None else src.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_size = src.stat().st_size
    check_free_space(dest_dir, required_bytes=src_size * 2)

    # 4. Conversion path resolution
    path = graph.pick(str(detected), target_fmt)
    if path is None:
        raise CuttleError(
            code="E_UNSUPPORTED",
            user_message=f"Cannot convert from {detected} to {target_fmt}.",
            detail=f"No conversion path in registry between {detected} and {target_fmt}",
        )

    # 5. External tool verification
    for required_tool in path.requires:
        if not is_tool_available(required_tool):
            raise CuttleError(
                code="E_TOOL_MISSING",
                user_message=f"Required tool '{required_tool}' is not installed.",
                detail=f"Conversion requires tool binary '{required_tool}' in vendor/ or PATH",
            )

    # 6. Execute conversion in safe temp file
    intended_final = dest_dir / f"{src.stem}.{target_fmt}"

    with temp_output(intended_final) as tmp_out:
        if path.is_direct:
            # Single-hop conversion
            _run_single_edge(path.edges[0], src, tmp_out, prog_cb, cancel_token)
        else:
            # 2-hop conversion: src -> tmp_mid -> tmp_out
            e1, e2 = path.edges
            mid_target = dest_dir / f"intermediate_{src.stem}.{e1.dst}"

            with temp_output(mid_target) as tmp_mid:
                # Hop 1
                def hop1_prog(pct: float | None, msg: str = "") -> None:
                    scaled = pct * 0.5 if pct is not None else None
                    prog_cb(scaled, f"Step 1/2: {msg}")

                _run_single_edge(e1, src, tmp_mid, hop1_prog, cancel_token)

                # Hop 2
                def hop2_prog(pct: float | None, msg: str = "") -> None:
                    scaled = 50.0 + pct * 0.5 if pct is not None else None
                    prog_cb(scaled, f"Step 2/2: {msg}")

                _run_single_edge(e2, tmp_mid, tmp_out, hop2_prog, cancel_token)

        # 7. Atomic commit with collision avoidance
        committed_file = commit_output(tmp_out, dest_dir, src.stem, target_fmt)

    return ConvertResult(
        output=committed_file,
        quality=path.quality,
        warnings=warnings,
    )
