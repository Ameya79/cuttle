"""Format and conversion registry loader.

Loads and validates cuttle/registry/formats.toml and cuttle/registry/edges.toml.
Fails loudly on:
- unknown adapter names
- unknown format ids
- duplicate edges
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cuttle.engine.types import Edge, Quality

# Allowed adapter identifiers across all phases.
# Adding a new adapter requires explicitly adding it to this set.
KNOWN_ADAPTERS = frozenset(
    {
        "ffmpeg",
        "image",
        "libreoffice",
        "pandoc",
        "pdf",
        "pdf2docx",
        "ocr",
        "dwg",
        "image_pdf",
        "word",
    }
)

# Allowed format kinds.
ALLOWED_KINDS = frozenset({"video", "audio", "image", "document"})


@dataclass(frozen=True)
class FormatDef:
    """Definition of a supported file format from formats.toml."""

    id: str
    kind: str
    ext: tuple[str, ...]
    magic: str


@dataclass
class Registry:
    """The in-memory registry of all supported formats and conversion edges."""

    formats: dict[str, FormatDef]
    edges: list[Edge]

    def get_format(self, fmt_id: str) -> FormatDef | None:
        """Lookup a format definition by format ID."""
        return self.formats.get(fmt_id.lower())

    def edges_from(self, src_fmt: str) -> list[Edge]:
        """Return all direct outgoing edges from the given source format."""
        return [e for e in self.edges if e.src == src_fmt]


def default_registry_dir() -> Path:
    """Return the default registry folder path inside the cuttle package."""
    return Path(__file__).resolve().parent.parent / "registry"


def load_formats(formats_file: Path) -> dict[str, FormatDef]:
    """Parse and validate formats.toml."""
    if not formats_file.is_file():
        raise FileNotFoundError(f"Formats configuration not found: {formats_file}")

    with open(formats_file, "rb") as f:
        data = tomllib.load(f)

    raw_formats = data.get("formats", {})
    if not raw_formats:
        raise ValueError(f"No formats defined in {formats_file}")

    formats: dict[str, FormatDef] = {}
    for fmt_id, entry in raw_formats.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Format entry {fmt_id!r} must be a table")

        kind = entry.get("kind")
        if not kind or kind not in ALLOWED_KINDS:
            allowed = sorted(ALLOWED_KINDS)
            raise ValueError(
                f"Invalid or missing kind {kind!r} for format {fmt_id!r}. Allowed: {allowed}"
            )

        raw_ext = entry.get("ext", [])
        if isinstance(raw_ext, str):
            raw_ext = [raw_ext]
        elif not isinstance(raw_ext, list) or not raw_ext:
            raise ValueError(f"Format {fmt_id!r} must specify at least one extension in 'ext'")

        # Clean extensions (strip leading dot, lowercase)
        clean_ext = tuple(e.lstrip(".").lower() for e in raw_ext if isinstance(e, str))
        if not clean_ext:
            raise ValueError(f"Format {fmt_id!r} has no valid string extensions")

        magic = entry.get("magic")
        if not magic or not isinstance(magic, str):
            raise ValueError(f"Format {fmt_id!r} must have a non-empty string 'magic' specifier")

        formats[fmt_id.lower()] = FormatDef(
            id=fmt_id.lower(),
            kind=kind,
            ext=clean_ext,
            magic=magic,
        )

    return formats


def load_edges(edges_file: Path, formats: dict[str, FormatDef]) -> list[Edge]:
    """Parse and validate edges.toml against known formats and adapters."""
    if not edges_file.is_file():
        raise FileNotFoundError(f"Edges configuration not found: {edges_file}")

    with open(edges_file, "rb") as f:
        data = tomllib.load(f)

    raw_edges = data.get("edge", [])
    if not isinstance(raw_edges, list):
        raise ValueError(f"Edges file {edges_file} must contain a list of [[edge]] tables")

    edges: list[Edge] = []
    seen_pairs: set[tuple[str, str]] = set()

    for idx, item in enumerate(raw_edges):
        if not isinstance(item, dict):
            raise ValueError(f"Edge entry #{idx} is not a valid table")

        src = item.get("src")
        dst = item.get("dst")
        if not src or not isinstance(src, str):
            raise ValueError(f"Edge #{idx} is missing required string 'src'")
        if not dst or not isinstance(dst, str):
            raise ValueError(f"Edge #{idx} is missing required string 'dst'")

        src = src.lower()
        dst = dst.lower()

        # Check unknown format IDs
        if src not in formats:
            raise ValueError(
                f"Unknown source format {src!r} in edge #{idx}. "
                f"Must be defined in formats.toml. Known formats: {sorted(formats.keys())}"
            )
        if dst not in formats:
            raise ValueError(
                f"Unknown destination format {dst!r} in edge #{idx}. "
                f"Must be defined in formats.toml. Known formats: {sorted(formats.keys())}"
            )

        # Check duplicate edges
        pair = (src, dst)
        if pair in seen_pairs:
            raise ValueError(f"Duplicate edge detected for {src} -> {dst}")
        seen_pairs.add(pair)

        # Check adapter
        adapter = item.get("adapter")
        if not adapter or not isinstance(adapter, str):
            raise ValueError(f"Edge {src} -> {dst} is missing required string 'adapter'")
        if adapter not in KNOWN_ADAPTERS:
            raise ValueError(
                f"Unknown adapter {adapter!r} in edge {src} -> {dst}. "
                f"Allowed adapters: {sorted(KNOWN_ADAPTERS)}"
            )

        # Check quality
        quality_raw = item.get("quality")
        try:
            quality = Quality(str(quality_raw).lower())
        except ValueError as err:
            allowed_q = [q.value for q in Quality]
            raise ValueError(
                f"Invalid quality {quality_raw!r} in edge {src} -> {dst}. Allowed: {allowed_q}"
            ) from err

        # Check cost
        cost = item.get("cost", 5)
        if not isinstance(cost, int) or cost < 1:
            raise ValueError(
                f"Invalid cost {cost!r} in edge {src} -> {dst}. Must be positive integer."
            )

        # Check label
        label = item.get("label")
        if not label or not isinstance(label, str):
            raise ValueError(f"Edge {src} -> {dst} is missing required string 'label'")

        # Requires & options
        requires_raw = item.get("requires", ())
        if isinstance(requires_raw, list):
            requires = tuple(str(r) for r in requires_raw)
        else:
            requires = tuple(requires_raw)

        options: dict[str, str] = {}
        options_raw: Any = item.get("options", {})
        if isinstance(options_raw, dict):
            options = {str(k): str(v) for k, v in options_raw.items()}

        edges.append(
            Edge(
                src=src,
                dst=dst,
                adapter=adapter,
                quality=quality,
                cost=cost,
                label=label,
                requires=requires,
                options=options,
            )
        )

    return edges


def load_registry(registry_dir: Path | None = None) -> Registry:
    """Load and validate full registry from directory.

    Fails loudly with ValueError or FileNotFoundError if any check fails.
    """
    base_dir = registry_dir or default_registry_dir()
    formats = load_formats(base_dir / "formats.toml")
    edges = load_edges(base_dir / "edges.toml", formats)
    return Registry(formats=formats, edges=edges)
