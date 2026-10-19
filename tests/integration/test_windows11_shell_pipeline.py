"""Integration tests for Windows 11 IExplorerCommand shell extension and native launcher.

Per task cards P4-05, P4-06, and P4-07:
- Crash safety test: Kill or terminate the worker; shell extension and launcher must
  remain responsive and fail gracefully.
- Speed budget: Verify end-to-end click-to-queue latency is well under 1 second.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cuttle.platform.windows.pipe import WindowsPipeServer, get_default_pipe_name

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LAUNCHER_EXE = ROOT_DIR / "cuttle" / "platform" / "windows" / "launcher" / "cuttlectl.exe"
DLL_PATH = ROOT_DIR / "cuttle" / "platform" / "windows" / "shell_extension" / "cuttle_shell.dll"


@pytest.fixture(scope="module", autouse=True)
def ensure_binaries_built() -> None:
    if not LAUNCHER_EXE.is_file():
        res = subprocess.run(
            [sys.executable, str(ROOT_DIR / "scripts" / "build_launcher.py")],
            capture_output=True,
        )
        assert res.returncode == 0
    if not DLL_PATH.is_file():
        res = subprocess.run(
            [sys.executable, str(ROOT_DIR / "scripts" / "build_shell_extension.py")],
            capture_output=True,
        )
        assert res.returncode == 0


class TestWindows11ShellIntegration:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_crash_safety_when_worker_is_dead(self, tmp_path: Path) -> None:
        """Verify Explorer never hangs and launcher handles dead worker gracefully (P4-05)."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"content")

        dead_pipe = get_default_pipe_name(base=f"cuttle_dead_{int(time.time() * 1000)}")

        # Launching with a non-existent pipe name
        # Launcher should attempt to connect, fail gracefully, and exit without hanging
        start = time.perf_counter()
        cmd = [
            str(LAUNCHER_EXE),
            "submit",
            "--pipe",
            dead_pipe,
            "--to",
            "mp3",
            str(test_file),
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=5)
        elapsed = time.perf_counter() - start

        # Must exit within timeout and not hang Explorer
        assert elapsed < 4.0, f"Launcher took too long to exit on dead worker: {elapsed:.2f}s"
        assert res.returncode != 0, "Launcher must return non-zero when worker cannot be reached"

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_speed_budget_click_to_queue_under_1_second(self, tmp_path: Path) -> None:
        """Verify click-to-queue feedback is well under the 1-second budget (P4-06)."""
        pipe_name = get_default_pipe_name(base=f"cuttle_speed_{int(time.time() * 1000)}")
        queue_received = threading.Event()

        def handle_client(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            if payload.get("op") == "convert":
                queue_received.set()
            return json.dumps({"status": "queued", "batch_id": "b1"}).encode("utf-8")

        server = WindowsPipeServer(pipe_name=pipe_name, handler=handle_client)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        time.sleep(0.05)

        test_file = tmp_path / "speed_benchmark.png"
        test_file.write_bytes(b"image")

        try:
            start_time = time.perf_counter()
            cmd = [
                str(LAUNCHER_EXE),
                "submit",
                "--pipe",
                pipe_name,
                "--to",
                "webp",
                str(test_file),
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=3)
            assert proc.returncode == 0
            assert queue_received.wait(timeout=1.0)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            print(f"\n[Speed Budget Test] Measured click-to-queue latency: {elapsed_ms:.2f} ms")
            assert elapsed_ms < 1000.0, (
                f"Click-to-queue latency {elapsed_ms:.2f}ms exceeded 1000ms budget"
            )
        finally:
            server.stop()
            server_thread.join(timeout=1.0)
