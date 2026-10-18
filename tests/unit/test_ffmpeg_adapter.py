"""Tests for cuttle/adapters/ffmpeg.py (P1-09).

Per TRD task card P1-09:
- Argv builder unit tests for every recipe (no FFmpeg needed)
- Integration: video_av.mp4 to mp3, wav, gif, webm all validate
- Progress values never decrease (monotonically non-decreasing)
- video_silent.mp4 to mp3 raises E_UNSUPPORTED with: 'This video has no audio to extract.'
- truncated.mp4 raises E_SRC_CORRUPT or E_TOOL_FAILED and leaves no temp file
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cuttle.adapters.ffmpeg import FFmpegAdapter, find_tool
from cuttle.engine.errors import CuttleError
from cuttle.engine.safe_output import temp_output
from cuttle.engine.types import CancelToken

# --- Unit Tests: Argv Builder (No FFmpeg binary required) ---


class TestArgvBuilder:
    @pytest.fixture
    def adapter(self) -> FFmpegAdapter:
        return FFmpegAdapter(ffmpeg_bin="ffmpeg_mock", ffprobe_bin="ffprobe_mock")

    def test_mp3_recipe(self, adapter: FFmpegAdapter) -> None:
        src = Path("/tmp/video.mp4")
        tmp = Path("/tmp/video.mp3.cuttle-part")
        argv = adapter.build_argv(src, "mp3", tmp)

        assert argv[0] == "ffmpeg_mock"
        assert "-vn" in argv
        assert [argv[argv.index("-c:a")], argv[argv.index("-c:a") + 1]] == ["-c:a", "libmp3lame"]
        assert [argv[argv.index("-q:a")], argv[argv.index("-q:a") + 1]] == ["-q:a", "2"]
        assert [argv[argv.index("-progress")], argv[argv.index("-progress") + 1]] == [
            "-progress",
            "pipe:1",
        ]
        assert [argv[argv.index("-f")], argv[argv.index("-f") + 1]] == ["-f", "mp3"]
        assert argv[-1] == str(tmp)

    def test_wav_recipe(self, adapter: FFmpegAdapter) -> None:
        src = Path("/tmp/video.mp4")
        tmp = Path("/tmp/video.wav.cuttle-part")
        argv = adapter.build_argv(src, "wav", tmp)

        assert argv[0] == "ffmpeg_mock"
        assert "-vn" in argv
        assert [argv[argv.index("-c:a")], argv[argv.index("-c:a") + 1]] == ["-c:a", "pcm_s16le"]
        assert [argv[argv.index("-f")], argv[argv.index("-f") + 1]] == ["-f", "wav"]
        assert argv[-1] == str(tmp)

    def test_mp4_recipe(self, adapter: FFmpegAdapter) -> None:
        src = Path("/tmp/video.mkv")
        tmp = Path("/tmp/video.mp4.cuttle-part")
        argv = adapter.build_argv(src, "mp4", tmp)

        assert argv[0] == "ffmpeg_mock"
        assert [argv[argv.index("-c:v")], argv[argv.index("-c:v") + 1]] == ["-c:v", "libx264"]
        assert [argv[argv.index("-preset")], argv[argv.index("-preset") + 1]] == [
            "-preset",
            "medium",
        ]
        assert [argv[argv.index("-crf")], argv[argv.index("-crf") + 1]] == ["-crf", "20"]
        assert [argv[argv.index("-c:a")], argv[argv.index("-c:a") + 1]] == ["-c:a", "aac"]
        assert [argv[argv.index("-b:a")], argv[argv.index("-b:a") + 1]] == ["-b:a", "192k"]
        assert [argv[argv.index("-movflags")], argv[argv.index("-movflags") + 1]] == [
            "-movflags",
            "+faststart",
        ]
        assert [argv[argv.index("-f")], argv[argv.index("-f") + 1]] == ["-f", "mp4"]

    def test_webm_recipe(self, adapter: FFmpegAdapter) -> None:
        src = Path("/tmp/video.mp4")
        tmp = Path("/tmp/video.webm.cuttle-part")
        argv = adapter.build_argv(src, "webm", tmp)

        assert argv[0] == "ffmpeg_mock"
        assert [argv[argv.index("-c:v")], argv[argv.index("-c:v") + 1]] == ["-c:v", "libvpx-vp9"]
        assert [argv[argv.index("-crf")], argv[argv.index("-crf") + 1]] == ["-crf", "32"]
        assert [argv[argv.index("-b:v")], argv[argv.index("-b:v") + 1]] == ["-b:v", "0"]
        assert [argv[argv.index("-c:a")], argv[argv.index("-c:a") + 1]] == ["-c:a", "libopus"]
        assert [argv[argv.index("-f")], argv[argv.index("-f") + 1]] == ["-f", "webm"]

    def test_gif_recipe(self, adapter: FFmpegAdapter) -> None:
        src = Path("/tmp/video.mp4")
        tmp = Path("/tmp/video.gif.cuttle-part")
        argv = adapter.build_argv(src, "gif", tmp)

        assert argv[0] == "ffmpeg_mock"
        assert "-vf" in argv
        assert "palettegen" in argv[argv.index("-vf") + 1]
        assert [argv[argv.index("-loop")], argv[argv.index("-loop") + 1]] == ["-loop", "0"]
        assert [argv[argv.index("-f")], argv[argv.index("-f") + 1]] == ["-f", "gif"]

    def test_unsupported_recipe_raises(self, adapter: FFmpegAdapter) -> None:
        with pytest.raises(CuttleError) as exc_info:
            adapter.build_argv(Path("foo.mp4"), "flv", Path("foo.flv"))
        assert exc_info.value.code == "E_UNSUPPORTED"


# --- Integration Tests: Live FFmpeg with Fixtures ---


class TestFFmpegIntegration:
    @pytest.fixture
    def adapter(self) -> FFmpegAdapter:
        return FFmpegAdapter()

    def test_silent_video_audio_extraction_raises_e_unsupported(
        self,
        adapter: FFmpegAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        """video_silent.mp4 to mp3 raises E_UNSUPPORTED: 'This video has no audio to extract.'"""
        silent = fixtures_dir / "video_silent.mp4"
        tmp_out = tmp_path / "silent.mp3.cuttle-part"

        with pytest.raises(CuttleError) as exc_info:
            adapter.plan(silent, "mp3", tmp_out, {})

        assert exc_info.value.code == "E_UNSUPPORTED"
        assert exc_info.value.user_message == "This video has no audio to extract."

    @pytest.mark.parametrize("dst_fmt", ["mp3", "wav", "gif", "webm"])
    def test_video_av_conversions_validate_and_progress_monotone(
        self,
        adapter: FFmpegAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
        dst_fmt: str,
    ) -> None:
        """video_av.mp4 converts to mp3, wav, gif, webm and validates."""
        src = fixtures_dir / "video_av.mp4"
        final_out = tmp_path / f"output.{dst_fmt}"
        tmp_out = tmp_path / f"output.{dst_fmt}.cuttle-part"

        plan = adapter.plan(src, dst_fmt, tmp_out, {})
        assert plan.duration_s is not None
        assert plan.duration_s > 0

        progress_log: list[float] = []

        def on_prog(pct: float | None, msg: str = "") -> None:
            if pct is not None:
                progress_log.append(pct)

        adapter.run(plan, on_prog, CancelToken())

        # Move tmp to final to test validation
        assert tmp_out.exists()
        tmp_out.rename(final_out)

        # Progress values must never decrease
        assert len(progress_log) > 0
        for i in range(len(progress_log) - 1):
            assert progress_log[i] <= progress_log[i + 1], "Progress values decreased!"

        # Final progress should reach 100
        assert progress_log[-1] == 100.0

        # Output must validate cleanly
        vr = adapter.validate(src, final_out)
        assert vr.ok is True, f"Validation failed: {vr.reason}"

    def test_truncated_mp4_raises_error_and_no_temp_file_remains(
        self,
        adapter: FFmpegAdapter,
        fixtures_dir: Path,
        tmp_path: Path,
    ) -> None:
        """truncated.mp4 raises E_SRC_CORRUPT or E_TOOL_FAILED, leaving no temp file."""
        src = fixtures_dir / "truncated.mp4"
        final_target = tmp_path / "truncated_out.mp3"

        with temp_output(final_target) as tmp_out:
            try:
                plan = adapter.plan(src, "mp3", tmp_out, {})
                adapter.run(plan, lambda pct, msg="": None, CancelToken())
            except CuttleError as err:
                assert err.code in {"E_SRC_CORRUPT", "E_TOOL_FAILED"}

        # Verify no temp file left behind
        assert not tmp_out.exists()

    def test_missing_tool_raises_e_tool_missing(self) -> None:
        with pytest.raises(CuttleError) as exc_info:
            find_tool("nonexistent_utility_12345")
        assert exc_info.value.code == "E_TOOL_MISSING"
