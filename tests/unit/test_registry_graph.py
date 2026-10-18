"""Tests for registry.py and graph.py (P1-04).

Per TRD task card P1-04:
- Default registry loads cleanly with all 14 Phase 1 formats
- Unknown adapter fails loudly
- Unknown format fails loudly
- Duplicate edge fails loudly
- Direct edge beats multi-hop
- 2-hop path gets the worst quality
- 3-hop path is never returned
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cuttle.engine.graph import ConversionGraph, build_graph
from cuttle.engine.registry import FormatDef, Registry, load_registry
from cuttle.engine.types import Edge, Quality

PHASE1_FORMATS = {
    "mp4",
    "mkv",
    "mov",
    "avi",
    "webm",
    "mp3",
    "wav",
    "gif",
    "png",
    "jpg",
    "webp",
    "bmp",
    "tiff",
    "heic",
}


# --- Registry Loading & Validation Tests ---


class TestRegistryLoading:
    def test_default_registry_loads_cleanly(self) -> None:
        """Production formats.toml and edges.toml must load cleanly."""
        registry = load_registry()
        assert len(registry.formats) >= len(PHASE1_FORMATS)
        assert PHASE1_FORMATS.issubset(set(registry.formats.keys()))
        assert len(registry.edges) > 0

    def test_all_formats_have_valid_fields(self) -> None:
        """Every format must have non-empty kind, ext, and magic."""
        registry = load_registry()
        for fmt_id, fmt in registry.formats.items():
            assert fmt.id == fmt_id
            assert fmt.kind in {"video", "audio", "image", "document"}
            assert len(fmt.ext) > 0
            assert all(isinstance(e, str) and not e.startswith(".") for e in fmt.ext)
            assert isinstance(fmt.magic, str) and len(fmt.magic) > 0

    def test_unknown_adapter_fails_loudly(self, tmp_path: Path) -> None:
        """An edge specifying an unknown adapter must raise ValueError."""
        formats_file = tmp_path / "formats.toml"
        formats_file.write_text(
            '[formats.mp4]\nkind = "video"\next = ["mp4"]\nmagic = "ftyp"\n'
            '[formats.mp3]\nkind = "audio"\next = ["mp3"]\nmagic = "id3"\n'
        )
        edges_file = tmp_path / "edges.toml"
        edges_file.write_text(
            '[[edge]]\nsrc = "mp4"\ndst = "mp3"\nadapter = "magic_converter"\n'
            'quality = "lossy"\ncost = 3\nlabel = "MP3"\n'
        )

        with pytest.raises(ValueError, match="Unknown adapter"):
            load_registry(tmp_path)

    def test_unknown_format_fails_loudly(self, tmp_path: Path) -> None:
        """An edge referencing an undefined format ID must raise ValueError."""
        formats_file = tmp_path / "formats.toml"
        formats_file.write_text('[formats.mp4]\nkind = "video"\next = ["mp4"]\nmagic = "ftyp"\n')
        edges_file = tmp_path / "edges.toml"
        edges_file.write_text(
            '[[edge]]\nsrc = "mp4"\ndst = "flac"\nadapter = "ffmpeg"\n'
            'quality = "lossy"\ncost = 3\nlabel = "FLAC"\n'
        )

        with pytest.raises(ValueError, match="Unknown destination format"):
            load_registry(tmp_path)

    def test_duplicate_edge_fails_loudly(self, tmp_path: Path) -> None:
        """Two edges with the exact same (src, dst) must raise ValueError."""
        formats_file = tmp_path / "formats.toml"
        formats_file.write_text(
            '[formats.mp4]\nkind = "video"\next = ["mp4"]\nmagic = "ftyp"\n'
            '[formats.mp3]\nkind = "audio"\next = ["mp3"]\nmagic = "id3"\n'
        )
        edges_file = tmp_path / "edges.toml"
        edges_file.write_text(
            '[[edge]]\nsrc = "mp4"\ndst = "mp3"\nadapter = "ffmpeg"\n'
            'quality = "lossy"\ncost = 3\nlabel = "MP3 (first)"\n\n'
            '[[edge]]\nsrc = "mp4"\ndst = "mp3"\nadapter = "ffmpeg"\n'
            'quality = "lossy"\ncost = 3\nlabel = "MP3 (duplicate)"\n'
        )

        with pytest.raises(ValueError, match="Duplicate edge detected"):
            load_registry(tmp_path)

    def test_invalid_quality_fails_loudly(self, tmp_path: Path) -> None:
        """An invalid quality string must raise ValueError."""
        formats_file = tmp_path / "formats.toml"
        formats_file.write_text(
            '[formats.mp4]\nkind = "video"\next = ["mp4"]\nmagic = "ftyp"\n'
            '[formats.mp3]\nkind = "audio"\next = ["mp3"]\nmagic = "id3"\n'
        )
        edges_file = tmp_path / "edges.toml"
        edges_file.write_text(
            '[[edge]]\nsrc = "mp4"\ndst = "mp3"\nadapter = "ffmpeg"\n'
            'quality = "ultra_hd"\ncost = 3\nlabel = "MP3"\n'
        )

        with pytest.raises(ValueError, match="Invalid quality"):
            load_registry(tmp_path)


# --- Graph Routing & Path-Finding Tests ---


def create_mock_registry(edges: list[Edge]) -> Registry:
    """Helper to create an in-memory registry with formats derived from edges."""
    format_ids = {e.src for e in edges} | {e.dst for e in edges}
    formats = {fid: FormatDef(id=fid, kind="video", ext=(fid,), magic=fid) for fid in format_ids}
    return Registry(formats=formats, edges=edges)


class TestGraphRouting:
    def test_direct_edge_beats_multi_hop(self) -> None:
        """Direct edge must always be chosen over a multi-hop path."""
        # a -> c direct (expensive, lossy)
        # a -> b -> c multi-hop (cheaper, lossless)
        direct_edge = Edge(
            src="a",
            dst="c",
            adapter="ffmpeg",
            quality=Quality.LOSSY,
            cost=10,
            label="Direct A->C",
        )
        hop1 = Edge(
            src="a",
            dst="b",
            adapter="ffmpeg",
            quality=Quality.LOSSLESS,
            cost=1,
            label="A->B",
        )
        hop2 = Edge(
            src="b",
            dst="c",
            adapter="ffmpeg",
            quality=Quality.LOSSLESS,
            cost=1,
            label="B->C",
        )

        reg = create_mock_registry([direct_edge, hop1, hop2])
        graph = ConversionGraph(reg)

        path = graph.pick("a", "c")
        assert path is not None
        assert path.is_direct is True
        assert len(path.edges) == 1
        assert path.edges[0] == direct_edge
        assert path.quality == Quality.LOSSY

    def test_two_hop_path_gets_worst_quality(self) -> None:
        """Multi-hop path quality must be the lowest in the chain."""
        # Case 1: LOSSLESS + LOSSY -> LOSSY
        e1 = Edge("a", "b", "ffmpeg", Quality.LOSSLESS, 2, "A->B")
        e2 = Edge("b", "c", "ffmpeg", Quality.LOSSY, 3, "B->C")
        reg1 = create_mock_registry([e1, e2])
        graph1 = ConversionGraph(reg1)

        path1 = graph1.pick("a", "c")
        assert path1 is not None
        assert path1.is_direct is False
        assert len(path1.edges) == 2
        assert path1.quality == Quality.LOSSY

        # Case 2: LOSSY + BEST_EFFORT -> BEST_EFFORT
        e3 = Edge("b", "c", "ffmpeg", Quality.BEST_EFFORT, 3, "B->C")
        reg2 = create_mock_registry([e1, e3])
        graph2 = ConversionGraph(reg2)

        path2 = graph2.pick("a", "c")
        assert path2 is not None
        assert path2.quality == Quality.BEST_EFFORT

        # Case 3: LOSSLESS + LOSSLESS -> LOSSLESS
        e4 = Edge("b", "c", "ffmpeg", Quality.LOSSLESS, 1, "B->C")
        reg3 = create_mock_registry([e1, e4])
        graph3 = ConversionGraph(reg3)

        path3 = graph3.pick("a", "c")
        assert path3 is not None
        assert path3.quality == Quality.LOSSLESS

    def test_three_hop_path_is_never_returned(self) -> None:
        """3-hop path (a -> b -> c -> d) must never be returned."""
        e1 = Edge("a", "b", "ffmpeg", Quality.LOSSLESS, 1, "A->B")
        e2 = Edge("b", "c", "ffmpeg", Quality.LOSSLESS, 1, "B->C")
        e3 = Edge("c", "d", "ffmpeg", Quality.LOSSLESS, 1, "C->D")

        reg = create_mock_registry([e1, e2, e3])
        graph = ConversionGraph(reg)

        # 2-hop should succeed (a -> c)
        assert graph.pick("a", "c") is not None

        # 3-hop must return None (a -> d)
        assert graph.pick("a", "d") is None

    def test_same_format_returns_none(self) -> None:
        """Converting format to itself returns None."""
        graph = build_graph()
        assert graph.pick("mp4", "mp4") is None

    def test_list_targets_with_tool_requirements(self) -> None:
        """list_targets correctly marks availability based on required tools."""
        e1 = Edge(
            src="doc",
            dst="pdf",
            adapter="libreoffice",
            quality=Quality.LOSSLESS,
            cost=5,
            label="PDF",
            requires=("libreoffice",),
        )
        e2 = Edge(
            src="doc",
            dst="txt",
            adapter="pandoc",
            quality=Quality.LOSSLESS,
            cost=2,
            label="TXT",
            requires=("pandoc",),
        )

        reg = create_mock_registry([e1, e2])
        graph = ConversionGraph(reg)

        # LibreOffice installed, Pandoc missing
        targets = graph.list_targets("doc", available_tools={"libreoffice"})
        target_map = {t.fmt: t for t in targets}

        assert target_map["pdf"].available is True
        assert target_map["pdf"].missing is None

        assert target_map["txt"].available is False
        assert target_map["txt"].missing == "pandoc"
