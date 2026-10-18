"""Process execution engine with streaming, timeouts, cancellation, and tree-killing.

Per TRD §6.5, Hard rules, and task card P1-08:
- Runs an argv list with a timeout without shell execution.
- Streams stdout lines to a callback in real time via a non-blocking background reader.
- Honors CancelToken.
- Kills the whole process tree (child and grandchildren) via psutil on timeout or cancel.
- Raises CuttleError("E_TIMEOUT") or CuttleError("E_CANCELLED") appropriately.
"""

from __future__ import annotations

from collections.abc import Callable
import io
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil

from cuttle.engine.errors import CuttleError
from cuttle.engine.types import CancelToken


def kill_process_tree(pid: int) -> None:
    """Kill the process and all its children/grandchildren recursively via psutil."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def _read_stdout_stream(
    stream: io.TextIOBase | None,
    callback: Callable[[str], None] | None,
) -> None:
    """Read lines from stdout stream and pass them to callback."""
    if stream is None:
        return
    try:
        for line in iter(stream.readline, ""):
            if callback is not None:
                callback(line.rstrip("\r\n"))
    except (ValueError, OSError):
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def run_command(
    argv: list[str],
    *,
    timeout_s: float | None = None,
    on_stdout_line: Callable[[str], None] | None = None,
    cancel: CancelToken | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run an external command, streaming stdout, honoring CancelToken and timeout.

    Parameters:
        argv: Command arguments list (shell is never used).
        timeout_s: Maximum wall-clock seconds before terminating with E_TIMEOUT.
        on_stdout_line: Callback called with each line of stdout.
        cancel: Thread-safe CancelToken to abort execution.
        cwd: Optional working directory.
        env: Optional environment dictionary.

    Returns:
        Process exit code (0 on success).

    Raises:
        CuttleError("E_TIMEOUT"): If command exceeds timeout_s.
        CuttleError("E_CANCELLED"): If cancel.cancelled is set.
        CuttleError("E_TOOL_FAILED"): If process exits with non-zero returncode.
    """
    if cancel is not None and cancel.cancelled:
        raise CuttleError(
            code="E_CANCELLED",
            user_message="The conversion was cancelled.",
            detail="Cancelled before process start",
        )

    # Windows creation flag: suppress creation of separate console window
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=cwd,
        env=env,
        shell=False,
        creationflags=creationflags,
    )

    reader_thread: threading.Thread | None = None
    if proc.stdout is not None:
        reader_thread = threading.Thread(
            target=_read_stdout_stream,
            args=(proc.stdout, on_stdout_line),
            daemon=True,
        )
        reader_thread.start()

    start_time = time.monotonic()

    try:
        while proc.poll() is None:
            # 1. Check cancellation
            if cancel is not None and cancel.cancelled:
                kill_process_tree(proc.pid)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                raise CuttleError(
                    code="E_CANCELLED",
                    user_message="The conversion was cancelled.",
                    detail=f"Cancelled by user token, killed pid {proc.pid}",
                )

            # 2. Check timeout
            elapsed = time.monotonic() - start_time
            if timeout_s is not None and elapsed > timeout_s:
                kill_process_tree(proc.pid)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                raise CuttleError(
                    code="E_TIMEOUT",
                    user_message="The conversion took too long and was stopped.",
                    detail=f"Exceeded timeout of {timeout_s}s, killed pid {proc.pid}",
                )

            time.sleep(0.02)

        # Process exited on its own
        retcode = proc.wait()
        if reader_thread is not None:
            reader_thread.join(timeout=1.0)

        stderr_text = ""
        if proc.stderr is not None:
            stderr_text = proc.stderr.read()

        if retcode != 0:
            if cancel is not None and cancel.cancelled:
                raise CuttleError(
                    code="E_CANCELLED",
                    user_message="The conversion was cancelled.",
                    detail=f"Process exited {retcode} following cancellation: {stderr_text.strip()}",
                )
            raise CuttleError(
                code="E_TOOL_FAILED",
                user_message="The conversion tool failed.",
                detail=stderr_text.strip() or f"Process exited with status {retcode}",
            )

        return retcode

    except (CuttleError, Exception):
        kill_process_tree(proc.pid)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        if reader_thread is not None:
            reader_thread.join(timeout=0.5)
        raise
