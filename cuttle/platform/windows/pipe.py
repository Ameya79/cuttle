"""Windows Named Pipe server and client IPC primitives.

Per TRD §6.8 and task card P2-04:
- Exposes get_default_pipe_name() scoped per user session (\\\\.\\pipe\\cuttle-<username>).
- WindowsPipeServer creates and loops on message-mode duplex named pipe instances.
- call_pipe() provides fast request-response IPC with automatic retry on pipe busy/connecting.
"""

from __future__ import annotations

import contextlib
import getpass
import time
from collections.abc import Callable
from typing import Any

try:
    import pywintypes
    import win32api
    import win32con
    import win32file
    import win32pipe
except ImportError:  # pragma: no cover
    pywintypes = None
    win32api = None
    win32con = None
    win32file = None
    win32pipe = None

BUF_SIZE = 65536


def get_default_pipe_name(base: str = "cuttle") -> str:
    """Return session-scoped Windows named pipe path."""
    username = getpass.getuser() or "default"
    safe_user = "".join(c for c in username if c.isalnum() or c in ("-", "_"))
    return rf"\\.\pipe\{base}-{safe_user}"


def call_pipe(pipe_name: str, payload: bytes, timeout_ms: int = 3000) -> bytes:
    """Send payload to named pipe and return response bytes with retry on busy/connecting."""
    if win32pipe is None:
        raise RuntimeError("pywin32 is required to call Windows Named Pipes.")

    start = time.monotonic()
    while True:
        try:
            res = win32pipe.CallNamedPipe(pipe_name, payload, BUF_SIZE, timeout_ms)
            return bytes(res)
        except Exception as e:
            err_code = getattr(e, "winerror", None)
            if err_code is None and hasattr(e, "args") and e.args:
                err_code = e.args[0] if isinstance(e.args[0], int) else None

            # 2: ERROR_FILE_NOT_FOUND (pipe server starting)
            # 231: ERROR_PIPE_BUSY (another client currently connecting)
            if err_code in (2, 231):
                elapsed_ms = (time.monotonic() - start) * 1000
                if elapsed_ms > timeout_ms:
                    raise TimeoutError(f"Timed out waiting for pipe {pipe_name}") from e
                time.sleep(0.02)
            else:
                raise


class WindowsPipeServer:
    """Multi-instance message-mode Named Pipe server loop."""

    def __init__(
        self,
        pipe_name: str,
        handler: Callable[[bytes], bytes],
    ) -> None:
        if win32pipe is None or win32file is None or win32api is None:
            raise RuntimeError("pywin32 is required to run Windows Named Pipe Server.")

        self.pipe_name = pipe_name
        self._handler = handler
        self._stopped = False

    @property
    def is_stopped(self) -> bool:
        return self._stopped

    def run(self) -> None:
        """Run the server accept loop (blocks until stop() is called)."""
        while not self._stopped:
            try:
                handle = win32pipe.CreateNamedPipe(
                    self.pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE
                    | win32pipe.PIPE_READMODE_MESSAGE
                    | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    BUF_SIZE,
                    BUF_SIZE,
                    0,
                    None,
                )
            except Exception:
                if self._stopped:
                    break
                time.sleep(0.05)
                continue

            try:
                # Wait for client to connect
                win32pipe.ConnectNamedPipe(handle, None)
                if self._stopped:
                    with contextlib.suppress(Exception):
                        win32file.WriteFile(handle, b'{"status":"stopping"}')
                    self._close_handle(handle)
                    break

                # Read message
                _, data = win32file.ReadFile(handle, BUF_SIZE)
                response = self._handler(data)
                win32file.WriteFile(handle, response)
            except Exception:
                pass
            finally:
                self._close_handle(handle)

    def _close_handle(self, handle: Any) -> None:
        if win32pipe is not None and win32api is not None:
            with contextlib.suppress(Exception):
                win32pipe.DisconnectNamedPipe(handle)
            with contextlib.suppress(Exception):
                win32api.CloseHandle(handle)

    def stop(self) -> None:
        """Signal server to stop and unblock any waiting accept call."""
        if self._stopped:
            return
        self._stopped = True
        # Send wake signal to unblock ConnectNamedPipe
        with contextlib.suppress(Exception):
            if win32pipe is not None:
                win32pipe.CallNamedPipe(self.pipe_name, b'{"op":"shutdown"}', 1024, 500)
