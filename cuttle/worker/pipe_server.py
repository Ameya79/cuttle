"""High-speed Windows Named Pipe IPC server and 300ms multi-select batcher.

Per TRD §6.8 and task card P2-04:
- Receives right-click commands over \\\\.\\pipe\\cuttle-<username>.
- 300ms Multi-Select Batching: bundles rapid consecutive explorer invocations into 1 batch.
- Handles JSON commands: convert, cancel_job, cancel_batch, ping.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cuttle.platform.windows.pipe import WindowsPipeServer, get_default_pipe_name
from cuttle.worker.queue import JobQueue


class BatchBuffer:
    """Collects rapid conversion requests within a trailing debounce window (default 300ms)."""

    def __init__(
        self,
        flush_cb: Callable[[str, list[tuple[Path, str]], Path | None], None],
        *,
        debounce_s: float = 0.3,
    ) -> None:
        self._flush_cb = flush_cb
        self._debounce_s = debounce_s
        self._lock = threading.Lock()
        self._current_batch_id: str | None = None
        self._current_items: list[tuple[Path, str]] = []
        self._current_out_dir: Path | None = None
        self._timer: threading.Timer | None = None

    @property
    def current_batch_id(self) -> str | None:
        with self._lock:
            return self._current_batch_id

    def add_item(
        self,
        src: Path,
        dst: str,
        *,
        out_dir: Path | None = None,
    ) -> str:
        """Add an item to the active batch window, resetting the debounce timer."""
        with self._lock:
            if self._current_batch_id is None:
                self._current_batch_id = str(uuid.uuid4())
                self._current_items = []
                self._current_out_dir = out_dir

            if self._timer is not None:
                self._timer.cancel()

            self._current_items.append((src, dst))
            batch_id = self._current_batch_id

            self._timer = threading.Timer(
                self._debounce_s,
                self._flush_batch,
                args=(batch_id,),
            )
            self._timer.daemon = True
            self._timer.start()

            return batch_id

    def _flush_batch(self, batch_id: str) -> None:
        """Invoked when the debounce timer fires."""
        items: list[tuple[Path, str]] = []
        out_dir: Path | None = None
        with self._lock:
            if self._current_batch_id == batch_id:
                items = list(self._current_items)
                out_dir = self._current_out_dir
                self._current_batch_id = None
                self._current_items = []
                self._current_out_dir = None
                self._timer = None

        if items:
            self._flush_cb(batch_id, items, out_dir)

    def flush_now(self) -> None:
        """Flush any pending batch immediately."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            batch_id = self._current_batch_id

        if batch_id is not None:
            self._flush_batch(batch_id)


class PipeServer:
    """Windows Named Pipe server receiving right-click requests and driving the JobQueue."""

    def __init__(
        self,
        queue: JobQueue,
        *,
        pipe_name: str | None = None,
        debounce_s: float = 0.3,
    ) -> None:
        self._queue = queue
        self._pipe_name = pipe_name or get_default_pipe_name()
        self._batch_buffer = BatchBuffer(
            self._on_batch_ready,
            debounce_s=debounce_s,
        )
        self._server = WindowsPipeServer(self._pipe_name, self._handle_raw_request)
        self._thread: threading.Thread | None = None

    @property
    def pipe_name(self) -> str:
        return self._pipe_name

    def _on_batch_ready(
        self,
        batch_id: str,
        items: list[tuple[Path, str]],
        out_dir: Path | None,
    ) -> None:
        """Dispatches a full batch of items to the JobQueue."""
        self._queue.submit_batch(batch_id, items, out_dir=out_dir)

    def _handle_raw_request(self, data: bytes) -> bytes:
        """Parse incoming JSON request, execute action, and return JSON response."""
        try:
            text = data.decode("utf-8").strip()
            if not text:
                return json.dumps({"status": "error", "message": "empty request"}).encode()
            req = json.loads(text)
            if not isinstance(req, dict):
                return json.dumps({"status": "error", "message": "payload must be object"}).encode()
        except Exception as e:
            return json.dumps({"status": "error", "message": f"invalid json: {e}"}).encode()

        op = req.get("op", "")
        response: dict[str, Any]

        if op == "ping":
            response = {"status": "ok", "message": "pong"}

        elif op == "convert":
            src_str = req.get("src")
            dst_fmt = req.get("dst")
            out_dir_str = req.get("out_dir")

            if not src_str or not dst_fmt:
                response = {
                    "status": "error",
                    "message": "convert operation requires 'src' and 'dst'",
                }
            else:
                src_path = Path(src_str)
                out_dir = Path(out_dir_str) if out_dir_str else None
                batch_id = self._batch_buffer.add_item(src_path, dst_fmt, out_dir=out_dir)
                response = {"status": "queued", "batch_id": batch_id}

        elif op == "cancel_job":
            job_id = req.get("job_id")
            if not job_id:
                response = {"status": "error", "message": "missing 'job_id'"}
            else:
                ok = self._queue.cancel_job(job_id)
                response = {"status": "ok", "cancelled": ok}

        elif op == "cancel_batch":
            target_batch_id = req.get("batch_id")
            if not target_batch_id:
                response = {"status": "error", "message": "missing 'batch_id'"}
            else:
                count = self._queue.cancel_batch(str(target_batch_id))
                response = {"status": "ok", "cancelled_count": count}

        elif op == "shutdown":
            response = {"status": "stopping"}

        else:
            response = {"status": "error", "message": f"unknown operation '{op}'"}

        return json.dumps(response).encode("utf-8")

    def start(self) -> None:
        """Start the Named Pipe server in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        # Brief pause to let pipe handle bind
        time.sleep(0.05)

    def stop(self) -> None:
        """Stop server, flush pending batch buffer, and join background thread."""
        self._batch_buffer.flush_now()
        self._server.stop()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def __enter__(self) -> PipeServer:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.stop()
