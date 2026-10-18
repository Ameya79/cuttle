"""Windows Job Object wrapper for atomic process-tree management and termination.

Per TRD §6.5 and task card P2-01:
- Configures JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE so child processes die if the job closes.
- Assigns processes to the job object so all children/grandchildren are tracked in kernel.
- TerminateJobObject kills all processes in the tree simultaneously.
"""

from __future__ import annotations

import contextlib
from typing import Any

try:
    import win32api
    import win32con
    import win32job
except ImportError:  # pragma: no cover
    win32api = None
    win32con = None
    win32job = None


class WindowsJobObject:
    """Encloses processes inside a Windows kernel Job Object for clean process-tree termination."""

    def __init__(self) -> None:
        if win32job is None or win32api is None or win32con is None:
            raise RuntimeError("pywin32 is required to use WindowsJobObject.")

        self._job: Any = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(
            self._job, win32job.JobObjectExtendedLimitInformation
        )
        info["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(
            self._job, win32job.JobObjectExtendedLimitInformation, info
        )
        self._closed = False

    def assign_process(self, pid: int) -> bool:
        """Assign a process to this Job Object by PID."""
        if self._closed or win32api is None or win32job is None:
            return False
        try:
            flags = win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE
            handle = win32api.OpenProcess(flags, False, pid)
            try:
                win32job.AssignProcessToJobObject(self._job, handle)
                return True
            finally:
                win32api.CloseHandle(handle)
        except Exception:
            return False

    def terminate(self, exit_code: int = 1) -> None:
        """Atomically kill all processes in the job object via the Windows kernel."""
        if self._closed or win32job is None:
            return
        with contextlib.suppress(Exception):
            win32job.TerminateJobObject(self._job, exit_code)

    def close(self) -> None:
        """Close the job object handle."""
        if self._closed:
            return
        self._closed = True
        if win32api is not None and self._job is not None:
            with contextlib.suppress(Exception):
                win32api.CloseHandle(self._job)

    def __enter__(self) -> WindowsJobObject:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()
