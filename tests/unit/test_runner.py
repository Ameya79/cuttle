"""Tests for engine/runner.py (P1-08).

Per TRD task card P1-08:
- A sleeping child is killed on timeout (raises E_TIMEOUT)
- Cancel kills a child that spawned a grandchild
- Streams stdout lines to a callback
- Honors CancelToken
- Never shell=True
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil
import pytest

from cuttle.engine.errors import CuttleError
from cuttle.engine.runner import kill_process_tree, run_command
from cuttle.engine.types import CancelToken


def test_runner_streams_stdout() -> None:
    """run_command correctly streams each stdout line to the callback."""
    code = "import sys; print('line 1'); print('line 2'); sys.stdout.flush()"
    captured: list[str] = []

    ret = run_command(
        [sys.executable, "-c", code],
        on_stdout_line=captured.append,
    )

    assert ret == 0
    assert captured == ["line 1", "line 2"]


def test_runner_timeout_kills_sleeping_child() -> None:
    """A sleeping child is killed when timeout_s is exceeded, raising E_TIMEOUT."""
    code = "import time; time.sleep(10)"
    start = time.monotonic()

    with pytest.raises(CuttleError) as exc_info:
        run_command(
            [sys.executable, "-c", code],
            timeout_s=0.3,
        )

    elapsed = time.monotonic() - start
    assert exc_info.value.code == "E_TIMEOUT"
    assert elapsed < 3.0  # Must terminate swiftly without waiting for full sleep


def test_runner_cancel_before_start_raises_e_cancelled() -> None:
    """If CancelToken is already cancelled, command is aborted without launching."""
    token = CancelToken()
    token.cancel()

    with pytest.raises(CuttleError) as exc_info:
        run_command([sys.executable, "-c", "print('should not run')"], cancel=token)

    assert exc_info.value.code == "E_CANCELLED"


def test_runner_cancel_kills_child_and_grandchild(tmp_path: Path) -> None:
    """Cancellation terminates both the child process and its spawned grandchild."""
    # Write PID recording file for grandchild
    pid_file = tmp_path / "grandchild.pid"

    # Child spawns a grandchild that sleeps, and child also sleeps
    grandchild_code = (
        f"import os, time; "
        f"open(r'{pid_file}', 'w').write(str(os.getpid())); "
        f"time.sleep(30)"
    )
    parent_code = (
        f"import subprocess, sys, time; "
        f"p = subprocess.Popen([sys.executable, '-c', {grandchild_code!r}]); "
        f"time.sleep(30)"
    )

    token = CancelToken()

    # Trigger cancel in a background thread after grandchild starts and writes PID
    def cancel_after_start() -> None:
        for _ in range(50):
            if pid_file.exists() and pid_file.read_text().strip():
                break
            time.sleep(0.05)
        time.sleep(0.1)
        token.cancel()

    thread = threading.Thread(target=cancel_after_start, daemon=True)
    thread.start()

    with pytest.raises(CuttleError) as exc_info:
        run_command(
            [sys.executable, "-c", parent_code],
            timeout_s=10.0,
            cancel=token,
        )

    thread.join(timeout=2.0)
    assert exc_info.value.code == "E_CANCELLED"

    # Verify grandchild was terminated
    assert pid_file.exists()
    grandchild_pid = int(pid_file.read_text().strip())
    assert not psutil.pid_exists(grandchild_pid) or not psutil.Process(grandchild_pid).is_running()


def test_runner_tool_failure_raises_e_tool_failed() -> None:
    """A non-zero process exit raises E_TOOL_FAILED with stderr detail."""
    code = "import sys; sys.stderr.write('Transcoding codec error'); sys.exit(2)"

    with pytest.raises(CuttleError) as exc_info:
        run_command([sys.executable, "-c", code])

    assert exc_info.value.code == "E_TOOL_FAILED"
    assert "Transcoding codec error" in exc_info.value.detail


def test_runner_never_uses_shell_true() -> None:
    """Hard rule: runner.py must never use shell=True."""
    runner_src = (
        Path(__file__).resolve().parent.parent.parent
        / "cuttle"
        / "engine"
        / "runner.py"
    ).read_text(encoding="utf-8")
    assert "shell=True" not in runner_src
    assert "shell=False" in runner_src
