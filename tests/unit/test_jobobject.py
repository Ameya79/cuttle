"""Unit tests for Windows Job Object process tree termination.

Per task card P2-01:
- Verifies WindowsJobObject initialization and limit flags.
- Verifies termination of child processes.
- Verifies termination of grandchild processes.
- Verifies JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE behavior.
- Verifies create_process_guard platform factory and NullProcessGuard fallback.
"""

from __future__ import annotations

import subprocess
import sys
import time

import psutil
import pytest

from cuttle.platform import NullProcessGuard, ProcessGuard, create_process_guard

# Only run WindowsJobObject tests on Windows
is_win = sys.platform == "win32"


def test_create_process_guard_protocol() -> None:
    guard = create_process_guard()
    assert isinstance(guard, ProcessGuard)
    assert hasattr(guard, "assign_process")
    assert hasattr(guard, "terminate")
    assert hasattr(guard, "close")
    guard.close()


def test_null_process_guard() -> None:
    guard = NullProcessGuard()
    assert guard.assign_process(12345) is True
    guard.terminate(1)
    guard.close()


@pytest.mark.skipif(not is_win, reason="Windows Job Objects are only supported on Windows")
class TestWindowsJobObject:
    def test_creation_and_close_idempotency(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        job = WindowsJobObject()
        job.close()
        # Closing multiple times should not raise
        job.close()

    def test_context_manager(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        with WindowsJobObject() as job:
            assert job._closed is False
        assert job._closed is True

    def test_assign_invalid_pid_returns_false(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        with WindowsJobObject() as job:
            # PID 99999999 should not exist
            result = job.assign_process(99999999)
            assert result is False

    def test_terminate_kills_child_process(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        with WindowsJobObject() as job:
            proc = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                assigned = job.assign_process(proc.pid)
                assert assigned is True
                assert psutil.pid_exists(proc.pid)

                job.terminate(exit_code=42)
                proc.wait(timeout=5)
                assert not psutil.pid_exists(proc.pid)
            finally:
                if proc.poll() is None:
                    proc.kill()

    def test_terminate_kills_child_and_grandchild(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        child_code = (
            "import subprocess, sys, time\n"
            "time.sleep(0.3)\n"
            "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "print(g.pid, flush=True)\n"
            "time.sleep(30)\n"
        )

        with WindowsJobObject() as job:
            proc = subprocess.Popen(
                [sys.executable, "-c", child_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            grandchild_pid: int | None = None
            try:
                # Assign parent immediately before grandchild spawns
                assigned = job.assign_process(proc.pid)
                assert assigned is True

                assert proc.stdout is not None
                line = proc.stdout.readline().strip()
                grandchild_pid = int(line)

                assert psutil.pid_exists(proc.pid)
                assert psutil.pid_exists(grandchild_pid)

                # Terminate the job object
                job.terminate(exit_code=99)
                proc.wait(timeout=5)

                # Both parent and grandchild must be dead
                time.sleep(0.2)
                assert not psutil.pid_exists(proc.pid)
                assert not psutil.pid_exists(grandchild_pid)
            finally:
                if proc.poll() is None:
                    proc.kill()
                if grandchild_pid is not None and psutil.pid_exists(grandchild_pid):
                    import contextlib

                    with contextlib.suppress(Exception):
                        psutil.Process(grandchild_pid).kill()

    def test_kill_on_job_close(self) -> None:
        from cuttle.platform.windows.jobobject import WindowsJobObject

        job = WindowsJobObject()
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            assigned = job.assign_process(proc.pid)
            assert assigned is True
            assert psutil.pid_exists(proc.pid)

            # Close the job handle — JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE must terminate child
            job.close()
            proc.wait(timeout=5)
            time.sleep(0.2)
            assert not psutil.pid_exists(proc.pid)
        finally:
            if proc.poll() is None:
                proc.kill()
