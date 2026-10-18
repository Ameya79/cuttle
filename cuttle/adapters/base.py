"""Base adapter interface and abstract class for format conversions.

Per TRD §6.2:
Every adapter implements:
- can_convert(src_fmt, dst_fmt) -> Quality | None
- plan(src, dst_fmt, tmp_out, options) -> Plan
- run(plan, on_progress, cancel) -> None
- validate(src, out) -> ValidationResult
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from cuttle.engine.types import (
    CancelToken,
    Plan,
    ProgressCb,
    Quality,
    ValidationResult,
)


class BaseAdapter(ABC):
    """Abstract base class for all conversion adapters in Cuttle."""

    @abstractmethod
    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Return the quality level if this adapter can perform the conversion, else None."""

    @abstractmethod
    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct the exact Plan (command argv and estimated duration) to execute."""

    @abstractmethod
    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute the conversion plan, reporting progress and honoring cancel."""

    @abstractmethod
    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate that the converted output file is valid and correctly formatted."""
