"""FFmpeg adapter for audio and video conversions.

Per TRD §6.4:
- Implements command recipes for mp4, webm, gif, mp3, wav.
- Progress parsing from '-progress pipe:1' with non-decreasing progress values.
- Validates output decode and duration within 1% of source duration.
- Refuses audio extraction from silent video with E_UNSUPPORTED:
  'This video has no audio to extract.'
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
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


def find_tool(tool_name: str) -> str:
    """Find the path to an external tool in vendor/ or system PATH."""
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).parent
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
    vendor_tool = project_root / "vendor" / f"{tool_name}.exe"
    if vendor_tool.is_file():
        return str(vendor_tool)

    system_tool = shutil.which(tool_name)
    if system_tool:
        return system_tool

    raise CuttleError(
        code="E_TOOL_MISSING",
        user_message=f"Required tool '{tool_name}' is not installed or missing.",
        detail=f"Looked in {vendor_tool} and system PATH",
    )


class FFmpegAdapter(BaseAdapter):
    """Adapter wrapping FFmpeg and FFprobe CLI tools."""

    SUPPORTED_TARGETS = frozenset({"mp4", "webm", "gif", "mp3", "wav"})

    def __init__(
        self,
        ffmpeg_bin: str | None = None,
        ffprobe_bin: str | None = None,
    ) -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._ffprobe_bin = ffprobe_bin

    @property
    def ffmpeg(self) -> str:
        """Resolve path to ffmpeg binary."""
        if self._ffmpeg_bin is None:
            self._ffmpeg_bin = find_tool("ffmpeg")
        return self._ffmpeg_bin

    @property
    def ffprobe(self) -> str:
        """Resolve path to ffprobe binary."""
        if self._ffprobe_bin is None:
            self._ffprobe_bin = find_tool("ffprobe")
        return self._ffprobe_bin

    def can_convert(self, src_fmt: str, dst_fmt: str) -> Quality | None:
        """Check if FFmpeg can convert src_fmt to dst_fmt."""
        src = src_fmt.lower()
        dst = dst_fmt.lower()

        if dst not in self.SUPPORTED_TARGETS:
            return None

        # Video sources
        if src in {"mp4", "mkv", "mov", "avi", "webm"}:
            if dst in {"mp4", "webm", "gif", "mp3"}:
                return Quality.LOSSY
            if dst == "wav":
                return Quality.LOSSLESS

        # Audio sources
        if src in {"mp3", "wav"}:
            if dst == "wav":
                return Quality.LOSSLESS
            if dst == "mp3":
                return Quality.LOSSY

        return None

    def probe(self, src: Path) -> dict[str, object]:
        """Probe media file using ffprobe, returning format duration and streams."""
        cmd = [
            self.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type",
            "-of",
            "json",
            str(src),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            raise CuttleError(
                code="E_SRC_CORRUPT",
                user_message=f"Could not read media file: {src.name}",
                detail=res.stderr.strip(),
            )

        try:
            data = json.loads(res.stdout)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object from ffprobe")
        except (json.JSONDecodeError, ValueError) as err:
            raise CuttleError(
                code="E_SRC_CORRUPT",
                user_message=f"Could not parse media metadata: {src.name}",
                detail=str(err),
            ) from err

        return data

    def get_duration(self, src: Path) -> float | None:
        """Return duration in seconds if known from ffprobe metadata, else None."""
        try:
            data = self.probe(src)
            format_info = data.get("format", {})
            if isinstance(format_info, dict) and "duration" in format_info:
                return float(format_info["duration"])
        except Exception:
            pass
        return None

    def has_audio_stream(self, src: Path) -> bool:
        """Return True if media file contains at least one audio stream."""
        try:
            data = self.probe(src)
            streams = data.get("streams", [])
            if isinstance(streams, list):
                return any(isinstance(s, dict) and s.get("codec_type") == "audio" for s in streams)
        except CuttleError:
            raise
        except Exception:
            pass
        return False

    def build_argv(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str] | None = None,
    ) -> list[str]:
        """Build exact command line argv matching TRD §6.4 recipes."""
        base = [self.ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
        prog = ["-progress", "pipe:1"]
        target = dst_fmt.lower()

        src_str = str(src)
        tmp_str = str(tmp_out)

        if target == "mp3":
            return [
                *base,
                "-i",
                src_str,
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2",
                *prog,
                "-f",
                "mp3",
                tmp_str,
            ]

        if target == "wav":
            return [
                *base,
                "-i",
                src_str,
                "-vn",
                "-c:a",
                "pcm_s16le",
                *prog,
                "-f",
                "wav",
                tmp_str,
            ]

        if target == "mp4":
            return [
                *base,
                "-i",
                src_str,
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                *prog,
                "-f",
                "mp4",
                tmp_str,
            ]

        if target == "webm":
            return [
                *base,
                "-i",
                src_str,
                "-c:v",
                "libvpx-vp9",
                "-crf",
                "32",
                "-b:v",
                "0",
                "-c:a",
                "libopus",
                *prog,
                "-f",
                "webm",
                tmp_str,
            ]

        if target == "gif":
            vf_filter = (
                "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
            )
            return [
                *base,
                "-i",
                src_str,
                "-vf",
                vf_filter,
                "-loop",
                "0",
                *prog,
                "-f",
                "gif",
                tmp_str,
            ]

        raise CuttleError(
            code="E_UNSUPPORTED",
            user_message=f"Unsupported conversion target: {target}",
            detail=f"FFmpeg recipe for target format '{target}' does not exist.",
        )

    def plan(
        self,
        src: Path,
        dst_fmt: str,
        tmp_out: Path,
        options: dict[str, str],
    ) -> Plan:
        """Construct the Plan, checking for audio stream if extracting audio."""
        target = dst_fmt.lower()

        # Check silent video audio extraction constraint
        if target in {"mp3", "wav"} and not self.has_audio_stream(src):
            raise CuttleError(
                code="E_UNSUPPORTED",
                user_message="This video has no audio to extract.",
                detail=f"Probed streams in {src.name} contained no audio codec.",
            )

        duration = self.get_duration(src)
        argv = self.build_argv(src, target, tmp_out, options)
        return Plan(args=argv, duration_s=duration)

    def run(
        self,
        plan: Plan,
        on_progress: ProgressCb,
        cancel: CancelToken,
    ) -> None:
        """Execute FFmpeg conversion, parsing progress monotonically."""
        duration_s = plan.duration_s
        last_percent: float = 0.0

        def parse_progress_line(line: str) -> None:
            nonlocal last_percent
            if line.startswith("out_time_us="):
                try:
                    val_str = line.split("=", 1)[1]
                    out_us = int(val_str)
                    if duration_s is not None and duration_s > 0:
                        calc_pct = (out_us / 1_000_000.0) / duration_s * 100.0
                        pct = max(last_percent, min(100.0, calc_pct))
                        last_percent = pct
                        on_progress(round(pct, 1), f"{round(pct, 1)}%")
                    else:
                        on_progress(None, "converting")
                except (ValueError, IndexError):
                    pass
            elif line.startswith("progress=end"):
                on_progress(100.0, "complete")

        run_command(
            plan.args,
            timeout_s=300.0,
            on_stdout_line=parse_progress_line,
            cancel=cancel,
        )

    def validate(self, src: Path, out: Path) -> ValidationResult:
        """Validate output file with ffprobe and check duration within 1%."""
        if not out.is_file() or out.stat().st_size == 0:
            return ValidationResult(ok=False, reason="Output file is missing or 0 bytes.")

        # Probe output with ffprobe
        cmd = [
            self.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            return ValidationResult(
                ok=False,
                reason=f"Output file failed ffprobe validation: {res.stderr.strip()}",
            )

        # GIF output has distinct duration calculation; skip 1% check for GIF
        if out.suffix.lower() == ".gif":
            return ValidationResult(ok=True)

        # Check duration if source duration is available
        src_dur = self.get_duration(src)
        out_dur = self.get_duration(out)

        if src_dur is not None and out_dur is not None and src_dur > 0:
            delta = abs(out_dur - src_dur) / src_dur
            if delta > 0.01:
                pct = delta * 100
                return ValidationResult(
                    ok=False,
                    reason=(
                        f"Output duration ({out_dur:.2f}s) differs from "
                        f"source ({src_dur:.2f}s) by {pct:.1f}% (> 1% limit)."
                    ),
                )

        return ValidationResult(ok=True)
