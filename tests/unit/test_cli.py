"""Unit tests for cuttle/cli.py (P1-12).

Per TRD task card P1-12:
- Tests typer commands: convert, targets, formats, doctor.
- Verifies exit codes 0, 1, 2, 3.
- Verifies --json mode emits only valid JSON (lines or object) with expected keys.
- Verifies doctor reports external tools and libraries cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cuttle.cli import app

runner = CliRunner()


class TestDoctorCommand:
    def test_doctor_human_readable(self) -> None:
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "Cuttle Doctor" in result.output
        assert "ffmpeg" in result.output
        assert "Pillow" in result.output
        assert "READY" in result.output

    def test_doctor_json_mode(self) -> None:
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["status"] == "ok"
        assert data["phase"] == 1
        assert data["tools"]["ffmpeg"]["installed"] is True
        assert data["libraries"]["Pillow"]["version"] is not None


class TestFormatsCommand:
    def test_formats_human_readable(self) -> None:
        result = runner.invoke(app, ["formats"])
        assert result.exit_code == 0
        assert "Registered formats:" in result.output
        assert "mp4" in result.output
        assert "png" in result.output

    def test_formats_json_mode(self) -> None:
        result = runner.invoke(app, ["formats", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert isinstance(data, dict)
        assert "mp4" in data
        assert "png" in data
        assert data["mp4"]["kind"] == "video"


class TestTargetsCommand:
    def test_targets_human_readable(self, fixtures_dir: Path) -> None:
        src = fixtures_dir / "img.png"
        result = runner.invoke(app, ["targets", str(src)])
        assert result.exit_code == 0
        assert "Available conversion targets" in result.output
        assert "jpg" in result.output
        assert "bmp" in result.output

    def test_targets_json_mode(self, fixtures_dir: Path) -> None:
        src = fixtures_dir / "img.png"
        result = runner.invoke(app, ["targets", str(src), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert isinstance(data, list)
        fmts = [t["fmt"] for t in data]
        assert "jpg" in fmts
        assert "bmp" in fmts

    def test_targets_missing_source_exits_code_1(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.png"
        result = runner.invoke(app, ["targets", str(missing)])
        assert result.exit_code == 1
        assert "E_SRC_MISSING" in result.output

    def test_targets_missing_source_json_mode(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.png"
        result = runner.invoke(app, ["targets", str(missing), "--json"])
        assert result.exit_code == 1
        data = json.loads(result.output.strip())
        assert data["type"] == "error"
        assert data["code"] == "E_SRC_MISSING"


class TestConvertCommand:
    def test_convert_human_readable(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "img.png"
        out_dir = tmp_path / "cli_out"
        result = runner.invoke(app, ["convert", str(src), "--to", "jpg", "--out", str(out_dir)])
        assert result.exit_code == 0
        assert "Converted:" in result.output
        assert "[lossy]" in result.output
        assert (out_dir / "img (converted).jpg").is_file()

    def test_convert_json_mode_streams_ndjson(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "img.png"
        out_dir = tmp_path / "cli_json_out"
        result = runner.invoke(
            app, ["convert", str(src), "--to", "bmp", "--out", str(out_dir), "--json"]
        )
        assert result.exit_code == 0

        # Each non-empty line must be valid JSON
        lines = [line.strip() for line in result.output.strip().splitlines() if line.strip()]
        assert len(lines) >= 2
        payloads = [json.loads(line) for line in lines]

        # Verify progress payloads
        progress_msgs = [p for p in payloads if p.get("type") == "progress"]
        assert len(progress_msgs) > 0

        # Verify success payload
        success = next(p for p in payloads if p.get("type") == "success")
        assert "img (converted).bmp" in success["output"]
        assert success["quality"] == "lossless"

    def test_convert_user_error_exits_code_1(self, fixtures_dir: Path, tmp_path: Path) -> None:
        src = fixtures_dir / "zero_byte.mp4"
        result = runner.invoke(
            app, ["convert", str(src), "--to", "mp3", "--out", str(tmp_path), "--json"]
        )
        assert result.exit_code == 1
        lines = [json.loads(line) for line in result.output.strip().splitlines() if line.strip()]
        error_line = next(p for p in lines if p.get("type") == "error")
        assert error_line["code"] == "E_SRC_CORRUPT"

    def test_convert_missing_required_arg_exits_code_2(self, fixtures_dir: Path) -> None:
        src = fixtures_dir / "img.png"
        # Missing required --to option
        result = runner.invoke(app, ["convert", str(src)])
        assert result.exit_code == 2

    def test_convert_unexpected_crash_exits_code_3(
        self, fixtures_dir: Path, tmp_path: Path
    ) -> None:
        src = fixtures_dir / "img.png"
        with patch("cuttle.cli.engine_convert", side_effect=RuntimeError("Simulated engine crash")):
            result = runner.invoke(
                app, ["convert", str(src), "--to", "jpg", "--out", str(tmp_path), "--json"]
            )
            assert result.exit_code == 3
            data = json.loads(result.output.strip())
            assert data["type"] == "fatal"
            assert data["code"] == "E_INTERNAL"
            assert "Simulated engine crash" in data["detail"]
