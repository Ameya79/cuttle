"""Core types for the Cuttle conversion engine.

These types define the data structures used throughout the engine.
Signatures are fixed per the TRD §6.2 — do not change without asking.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class Quality(StrEnum):
    """How much fidelity the conversion preserves."""

    LOSSLESS = "lossless"
    LOSSY = "lossy"
    BEST_EFFORT = "best_effort"


@dataclass(frozen=True)
class Edge:
    """One conversion path from a source format to a target format.

    Edges live in registry/edges.toml and are loaded by registry.py.
    """

    src: str  # format id from formats.toml, e.g. 'mp4'
    dst: str  # e.g. 'mp3'
    adapter: str  # e.g. 'ffmpeg'
    quality: Quality
    cost: int  # 1 cheap .. 10 expensive
    label: str  # shown in the menu, e.g. 'MP3 (audio)'
    requires: tuple[str, ...] = ()  # e.g. ('libreoffice',)
    options: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    """The exact command to run for a conversion.

    args is an argv list.  Never a shell string.
    """

    args: list[str]
    duration_s: float | None = None  # total length if known, for progress


@dataclass
class ValidationResult:
    """Result of validating a converted output file."""

    ok: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


class CancelToken:
    """Thread-safe cancellation signal for long-running conversions."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._cancelled


# Callback type: (percent 0..100 or None for indeterminate, message)
ProgressCb = Callable[[float | None, str], None]


class Adapter(Protocol):
    """Protocol that every converter adapter must implement.

    See TRD §6.2 for the full contract.
    """

    name: str

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Return the quality label if this adapter can do the conversion, else None."""
        ...

    def plan(self, src: Path, dst_fmt: str, tmp_out: Path, options: dict[str, str]) -> Plan:
        """Build the exact command (argv) to run."""
        ...

    def run(self, plan: Plan, on_progress: ProgressCb, cancel: CancelToken) -> None:
        """Execute the conversion, reporting progress and honoring cancel."""
        ...

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Check the output is sane (opens, correct duration/dimensions, etc.)."""
        ...


@dataclass
class ConvertResult:
    """Returned by engine.convert() on success."""

    output: Path
    quality: Quality
    warnings: list[str]


@dataclass(frozen=True)
class Target:
    """One possible target format for a given input file."""

    fmt: str
    label: str
    quality: Quality
    available: bool  # false if a required tool is missing
    missing: str | None = None  # e.g. 'libreoffice'
