"""Tests for engine/types.py and engine/errors.py (P1-03)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cuttle.engine.errors import ERROR_CODES, CuttleError
from cuttle.engine.types import (
    CancelToken,
    ConvertResult,
    Edge,
    Plan,
    Quality,
    Target,
    ValidationResult,
)

# --- Error codes ---


class TestErrorCodes:
    """ERROR_CODES must be a tuple of unique strings."""

    def test_codes_are_unique(self) -> None:
        assert len(ERROR_CODES) == len(set(ERROR_CODES))

    def test_codes_are_strings(self) -> None:
        for code in ERROR_CODES:
            assert isinstance(code, str)
            assert code.startswith("E_")

    def test_codes_are_non_empty(self) -> None:
        assert len(ERROR_CODES) > 0


# --- CuttleError ---


class TestCuttleError:
    """CuttleError stores code, user_message, and detail."""

    def test_keeps_all_fields(self) -> None:
        err = CuttleError("E_TIMEOUT", "The conversion took too long.", "killed pid 1234")
        assert err.code == "E_TIMEOUT"
        assert err.user_message == "The conversion took too long."
        assert err.detail == "killed pid 1234"
        # The Exception message is the user_message
        assert str(err) == "The conversion took too long."

    def test_detail_defaults_to_empty(self) -> None:
        err = CuttleError("E_SRC_MISSING", "File not found.")
        assert err.detail == ""

    def test_rejects_unknown_code(self) -> None:
        with pytest.raises(ValueError, match="Unknown error code"):
            CuttleError("E_BOGUS", "This should fail.")

    def test_is_exception(self) -> None:
        err = CuttleError("E_CANCELLED", "Cancelled.")
        assert isinstance(err, Exception)

    @pytest.mark.parametrize("code", ERROR_CODES)
    def test_all_codes_are_valid(self, code: str) -> None:
        """Every code in ERROR_CODES can be used without raising ValueError."""
        err = CuttleError(code, f"Test message for {code}.")
        assert err.code == code


# --- Quality enum ---


class TestQuality:
    def test_values(self) -> None:
        assert Quality.LOSSLESS.value == "lossless"
        assert Quality.LOSSY.value == "lossy"
        assert Quality.BEST_EFFORT.value == "best_effort"

    def test_string_comparison(self) -> None:
        # Quality is a str enum, so it can be compared to strings
        assert Quality.LOSSLESS == "lossless"


# --- Edge ---


class TestEdge:
    def test_frozen(self) -> None:
        edge = Edge(
            src="mp4",
            dst="mp3",
            adapter="ffmpeg",
            quality=Quality.LOSSY,
            cost=3,
            label="MP3 (audio)",
        )
        with pytest.raises(AttributeError):
            edge.src = "avi"  # type: ignore[misc]

    def test_defaults(self) -> None:
        edge = Edge(
            src="mp4",
            dst="mp3",
            adapter="ffmpeg",
            quality=Quality.LOSSY,
            cost=3,
            label="MP3 (audio)",
        )
        assert edge.requires == ()
        assert edge.options == {}

    def test_with_requires(self) -> None:
        edge = Edge(
            src="docx",
            dst="pdf",
            adapter="libreoffice",
            quality=Quality.LOSSLESS,
            cost=6,
            label="PDF",
            requires=("libreoffice",),
        )
        assert edge.requires == ("libreoffice",)


# --- Plan ---


class TestPlan:
    def test_args_list(self) -> None:
        p = Plan(args=["ffmpeg", "-i", "src.mp4", "out.mp3"])
        assert p.args == ["ffmpeg", "-i", "src.mp4", "out.mp3"]
        assert p.duration_s is None

    def test_with_duration(self) -> None:
        p = Plan(args=["ffmpeg"], duration_s=120.5)
        assert p.duration_s == 120.5


# --- ValidationResult ---


class TestValidationResult:
    def test_ok(self) -> None:
        vr = ValidationResult(ok=True)
        assert vr.ok is True
        assert vr.reason == ""
        assert vr.warnings == []

    def test_failed_with_reason(self) -> None:
        vr = ValidationResult(ok=False, reason="Duration mismatch")
        assert vr.ok is False
        assert vr.reason == "Duration mismatch"


# --- CancelToken ---


class TestCancelToken:
    def test_starts_not_cancelled(self) -> None:
        ct = CancelToken()
        assert ct.cancelled is False

    def test_cancel_sets_flag(self) -> None:
        ct = CancelToken()
        ct.cancel()
        assert ct.cancelled is True


# --- ConvertResult ---


class TestConvertResult:
    def test_fields(self) -> None:
        cr = ConvertResult(
            output=Path("out.mp3"),
            quality=Quality.LOSSY,
            warnings=["Some quality was lost."],
        )
        assert cr.output == Path("out.mp3")
        assert cr.quality == Quality.LOSSY
        assert cr.warnings == ["Some quality was lost."]


# --- Target ---


class TestTarget:
    def test_available(self) -> None:
        t = Target(fmt="mp3", label="MP3 (audio)", quality=Quality.LOSSY, available=True)
        assert t.available is True
        assert t.missing is None

    def test_unavailable_with_missing(self) -> None:
        t = Target(
            fmt="pdf",
            label="PDF",
            quality=Quality.LOSSLESS,
            available=False,
            missing="libreoffice",
        )
        assert t.available is False
        assert t.missing == "libreoffice"
