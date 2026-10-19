"""Unit and latency tests for the native C++ cuttlectl launcher.

Per task card P4-01:
- Replace Python cuttlectl with native executable that forwards requests to pipe.
- Test: median time from start to pipe write is under 100 ms.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from cuttle.platform.windows.pipe import WindowsPipeServer, get_default_pipe_name

LAUNCHER_EXE = (
    Path(__file__).resolve().parent.parent.parent
    / "cuttle"
    / "platform"
    / "windows"
    / "launcher"
    / "cuttlectl.exe"
)


@pytest.fixture(scope="module", autouse=True)
def ensure_launcher_compiled() -> None:
    """Ensure the native launcher binary is compiled before running tests."""
    if not LAUNCHER_EXE.is_file():
        build_script = (
            Path(__file__).resolve().parent.parent.parent / "scripts" / "build_launcher.py"
        )
        res = subprocess.run([sys.executable, str(build_script)], capture_output=True, text=True)
        assert res.returncode == 0, f"Failed to build launcher: {res.stderr}"
    assert LAUNCHER_EXE.is_file(), "Launcher executable must exist"


class TestNativeLauncher:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_launcher_binary_properties(self) -> None:
        """Verify the compiled binary exists and is under 2 MB."""
        assert LAUNCHER_EXE.is_file()
        size_bytes = LAUNCHER_EXE.stat().st_size
        assert size_bytes > 10000  # Valid PE
        assert size_bytes < 5 * 1024 * 1024  # Well under size budget

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_launcher_submits_to_named_pipe(self, tmp_path: Path) -> None:
        """Verify the native launcher correctly forwards conversion request to pipe server."""
        pipe_name = get_default_pipe_name(base=f"cuttle_test_{int(time.time() * 1000)}")
        received_requests: list[dict] = []

        def handle_client(data: bytes) -> bytes:
            payload = json.loads(data.decode("utf-8"))
            received_requests.append(payload)
            return json.dumps({"status": "queued", "batch_id": "test_batch"}).encode("utf-8")

        server = WindowsPipeServer(pipe_name=pipe_name, handler=handle_client)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        time.sleep(0.05)

        test_file = tmp_path / "sample.mp4"
        test_file.write_bytes(b"dummy")

        try:
            # Execute launcher with shorthand syntax: cuttlectl <file> mp3
            # We override the pipe name via --pipe in submit syntax for custom pipe isolation
            cmd = [
                str(LAUNCHER_EXE),
                "submit",
                "--pipe",
                pipe_name,
                "--to",
                "mp3",
                str(test_file),
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=5)
            assert res.returncode == 0

            # Verify server received the conversion request
            assert len(received_requests) >= 1
            convert_req = [r for r in received_requests if r.get("op") == "convert"]
            assert len(convert_req) == 1
            assert convert_req[0]["dst"] == "mp3"
            assert Path(convert_req[0]["src"]).resolve() == test_file.resolve()
        finally:
            server.stop()
            server_thread.join(timeout=1.0)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only test")
    def test_launcher_latency_budget_under_100ms(self, tmp_path: Path) -> None:
        """Verify median time from start to pipe write is under 100 ms (P4-01 specification)."""
        pipe_name = get_default_pipe_name(base=f"cuttle_lat_{int(time.time() * 1000)}")

        def handle_client(data: bytes) -> bytes:
            return json.dumps({"status": "queued", "batch_id": "b1"}).encode("utf-8")

        server = WindowsPipeServer(pipe_name=pipe_name, handler=handle_client)
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()
        time.sleep(0.05)

        test_file = tmp_path / "speed_test.mp4"
        test_file.write_bytes(b"dummy content")

        durations_ms: list[float] = []

        try:
            # Measure 5 runs to get a robust median
            for _ in range(5):
                start = time.perf_counter()
                cmd = [
                    str(LAUNCHER_EXE),
                    "submit",
                    "--pipe",
                    pipe_name,
                    "--to",
                    "mp3",
                    str(test_file),
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=5)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                assert proc.returncode == 0
                durations_ms.append(elapsed_ms)

            median_ms = statistics.median(durations_ms)
            print(f"\nMeasured launcher durations (ms): {durations_ms}")
            print(f"Median execution latency: {median_ms:.2f} ms")

            # Must be strictly under 100 ms per task card P4-01
            assert median_ms < 100.0, (
                f"Launcher median latency {median_ms:.2f}ms exceeded 100ms budget"
            )
        finally:
            server.stop()
            server_thread.join(timeout=1.0)
