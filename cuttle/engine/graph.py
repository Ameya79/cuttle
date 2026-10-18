"""Conversion graph and path routing.

Constructs the directed graph of format conversions and finds paths.
Rules:
- Direct edges beat multi-hop paths.
- Multi-hop paths are allowed up to 2 hops, only when no direct edge exists.
- The combined quality of a multi-hop path is the worst quality in the chain.
- 3-hop paths are never returned.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cuttle.engine.registry import Registry, load_registry
from cuttle.engine.types import Edge, Quality, Target

# Quality order: LOSSLESS is highest fidelity, BEST_EFFORT is lowest
QUALITY_RANK: dict[Quality, int] = {
    Quality.LOSSLESS: 3,
    Quality.LOSSY: 2,
    Quality.BEST_EFFORT: 1,
}


def worst_quality(qualities: Sequence[Quality]) -> Quality:
    """Return the lowest fidelity quality from a sequence."""
    if not qualities:
        return Quality.BEST_EFFORT
    return min(qualities, key=lambda q: QUALITY_RANK[q])


@dataclass(frozen=True)
class ConversionPath:
    """A resolved conversion path (direct or 2-hop)."""

    edges: tuple[Edge, ...]
    src: str
    dst: str
    quality: Quality
    cost: int
    label: str
    requires: tuple[str, ...]

    @property
    def is_direct(self) -> bool:
        """Whether this conversion is a single direct edge."""
        return len(self.edges) == 1

    @classmethod
    def from_single_edge(cls, edge: Edge) -> ConversionPath:
        """Construct a path from a single direct edge."""
        return cls(
            edges=(edge,),
            src=edge.src,
            dst=edge.dst,
            quality=edge.quality,
            cost=edge.cost,
            label=edge.label,
            requires=edge.requires,
        )

    @classmethod
    def from_two_edges(cls, e1: Edge, e2: Edge) -> ConversionPath:
        """Construct a 2-hop path aggregating quality and tools."""
        combined_qual = worst_quality((e1.quality, e2.quality))
        combined_cost = e1.cost + e2.cost
        combined_requires = tuple(sorted(set(e1.requires + e2.requires)))
        # Target label comes from the destination edge
        return cls(
            edges=(e1, e2),
            src=e1.src,
            dst=e2.dst,
            quality=combined_qual,
            cost=combined_cost,
            label=e2.label,
            requires=combined_requires,
        )


class ConversionGraph:
    """Graph of formats and conversion edges."""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        # Index direct edges by (src, dst)
        self._direct_edges: dict[tuple[str, str], Edge] = {
            (e.src, e.dst): e for e in registry.edges
        }
        # Index outgoing edges by src
        self._outgoing: dict[str, list[Edge]] = {}
        for fmt in registry.formats:
            self._outgoing[fmt] = []
        for e in registry.edges:
            self._outgoing.setdefault(e.src, []).append(e)

    def pick(self, src_fmt: str, dst_fmt: str) -> ConversionPath | None:
        """Find the best conversion path from src_fmt to dst_fmt.

        1. If a direct edge exists, it is ALWAYS returned.
        2. If no direct edge exists, 2-hop paths are searched.
        3. 3-hop paths are never returned (returns None).
        """
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if src == dst:
            return None

        # 1. Direct edge beats multi-hop
        direct = self._direct_edges.get((src, dst))
        if direct is not None:
            return ConversionPath.from_single_edge(direct)

        # 2. Check 2-hop paths (src -> mid -> dst)
        candidate_paths: list[ConversionPath] = []
        for e1 in self._outgoing.get(src, []):
            mid = e1.dst
            if mid in (src, dst):
                continue

            e2 = self._direct_edges.get((mid, dst))
            if e2 is not None:
                candidate_paths.append(ConversionPath.from_two_edges(e1, e2))

        if not candidate_paths:
            # 3. 3-hop paths are never returned
            return None

        # Sort candidate 2-hop paths:
        # Best quality first (highest rank), then lowest cost
        candidate_paths.sort(key=lambda p: (-QUALITY_RANK[p.quality], p.cost))
        return candidate_paths[0]

    def list_targets(
        self,
        src_fmt: str,
        available_tools: set[str] | None = None,
    ) -> list[Target]:
        """List all reachable target formats for the given source format.

        Direct edges are returned first; 2-hop destinations are added only
        if no direct edge exists to that target.
        """
        src = src_fmt.lower()
        if src not in self.registry.formats:
            return []

        # Find best path to all possible destination formats in registry
        targets: list[Target] = []
        for dst in sorted(self.registry.formats.keys()):
            if dst == src:
                continue

            path = self.pick(src, dst)
            if path is None:
                continue

            # Determine tool availability
            if available_tools is None:
                available = True
                missing = None
            else:
                missing_tools = [req for req in path.requires if req not in available_tools]
                available = len(missing_tools) == 0
                missing = missing_tools[0] if missing_tools else None

            targets.append(
                Target(
                    fmt=dst,
                    label=path.label,
                    quality=path.quality,
                    available=available,
                    missing=missing,
                )
            )

        # Sort targets: direct first (cost), then format name
        return targets


def build_graph(registry: Registry | None = None) -> ConversionGraph:
    """Create and return a ConversionGraph using the provided or default registry."""
    reg = registry or load_registry()
    return ConversionGraph(reg)
