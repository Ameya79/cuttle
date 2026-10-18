"""Concurrency controller and event-driven job queue for Cuttle background conversions.

Per TRD §6.6 and task card P2-03:
- Throttles parallel conversion jobs to max(1, cpu_count // 2).
- Emits real-time decoupled QueueEvents
  (job_queued, job_started, job_progress, job_done, batch_done).
- Supports instant per-job and per-batch cancellation via CancelToken and Windows Job Objects.
- Persists state updates to SQLite via cuttle.worker.db.JobDatabase.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from cuttle.engine.convert import convert
from cuttle.engine.errors import CuttleError
from cuttle.engine.registry import Registry
from cuttle.engine.types import CancelToken
from cuttle.worker.db import JobDatabase


class EventType(StrEnum):
    """Lifecycle events emitted during queued execution."""

    JOB_QUEUED = "job_queued"
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_DONE = "job_done"
    BATCH_DONE = "batch_done"


@dataclass(frozen=True)
class QueueEvent:
    """Immutable event payload broadcast to listeners."""

    event_type: EventType
    batch_id: str
    job_id: str | None
    src_path: str = ""
    dst_fmt: str = ""
    percent: float | None = None
    message: str = ""
    status: str | None = None  # 'success' | 'failed' | 'cancelled'
    output_path: str | None = None
    quality: str | None = None
    error_code: str | None = None
    error_msg: str | None = None
    timestamp: float = 0.0
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0


@dataclass
class _BatchTracker:
    total: int
    succeeded: int = 0
    failed: int = 0
    cancelled: int = 0
    job_ids: set[str] = field(default_factory=set)

    @property
    def is_complete(self) -> bool:
        return (self.succeeded + self.failed + self.cancelled) >= self.total


class JobQueue:
    """Manages parallel conversions with a concurrency cap and lifecycle event streaming."""

    def __init__(
        self,
        db: JobDatabase,
        *,
        max_workers: int | None = None,
        event_cb: Callable[[QueueEvent], None] | None = None,
        registry: Registry | None = None,
    ) -> None:
        self._db = db
        self._event_cb = event_cb
        self._registry = registry

        if max_workers is not None and max_workers > 0:
            self._max_workers = max_workers
        else:
            cpu = os.cpu_count() or 2
            self._max_workers = max(1, cpu // 2)

        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="cuttle-worker",
        )
        self._lock = threading.Lock()
        self._tokens: dict[str, CancelToken] = {}
        self._batch_trackers: dict[str, _BatchTracker] = {}
        self._futures: dict[str, concurrent.futures.Future[None]] = {}
        self._is_shutdown = False

    @property
    def max_workers(self) -> int:
        """Return the active concurrency cap."""
        return self._max_workers

    def _emit(self, event: QueueEvent) -> None:
        """Safely deliver an event to the registered callback."""
        if self._event_cb is not None:
            with contextlib.suppress(Exception):
                self._event_cb(event)

    def submit_job(
        self,
        batch_id: str,
        src_path: Path | str,
        dst_fmt: str,
        *,
        out_dir: Path | None = None,
    ) -> str:
        """Submit a single file conversion job; returns unique job_id."""
        job_id = str(uuid.uuid4())
        src_str = str(src_path)
        clean_fmt = dst_fmt.lower().lstrip(".")

        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Cannot submit job to a shutdown JobQueue")

            token = CancelToken()
            self._tokens[job_id] = token

            if batch_id not in self._batch_trackers:
                self._batch_trackers[batch_id] = _BatchTracker(total=1, job_ids={job_id})
            else:
                tracker = self._batch_trackers[batch_id]
                tracker.job_ids.add(job_id)
                if len(tracker.job_ids) > tracker.total:
                    tracker.total = len(tracker.job_ids)

            self._db.insert_job(job_id, batch_id, src_str, clean_fmt, state="queued")

            self._emit(
                QueueEvent(
                    event_type=EventType.JOB_QUEUED,
                    batch_id=batch_id,
                    job_id=job_id,
                    src_path=src_str,
                    dst_fmt=clean_fmt,
                    timestamp=time.time(),
                )
            )

            future = self._executor.submit(
                self._run_job,
                job_id,
                batch_id,
                Path(src_str),
                clean_fmt,
                out_dir,
                token,
            )
            self._futures[job_id] = future

        return job_id

    def submit_batch(
        self,
        batch_id: str,
        items: list[tuple[Path | str, str]],
        *,
        out_dir: Path | None = None,
    ) -> list[str]:
        """Submit multiple files as a single batch and return their job_ids."""
        if not items:
            return []

        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Cannot submit job to a shutdown JobQueue")
            if batch_id not in self._batch_trackers:
                self._batch_trackers[batch_id] = _BatchTracker(total=len(items))
            else:
                self._batch_trackers[batch_id].total += len(items)

        job_ids: list[str] = []
        for src_path, dst_fmt in items:
            jid = self.submit_job(batch_id, src_path, dst_fmt, out_dir=out_dir)
            job_ids.append(jid)
        return job_ids

    def _run_job(
        self,
        job_id: str,
        batch_id: str,
        src_path: Path,
        dst_fmt: str,
        out_dir: Path | None,
        cancel_token: CancelToken,
    ) -> None:
        """Executed inside a worker thread."""
        src_str = str(src_path)

        # 1. Pre-start cancellation check
        if cancel_token.cancelled:
            self._finish_job(
                job_id=job_id,
                batch_id=batch_id,
                src_path=src_str,
                dst_fmt=dst_fmt,
                status="cancelled",
                error_code="E_CANCELLED",
                error_msg="Cancelled before conversion started",
            )
            return

        # 2. Mark running
        self._db.update_state(job_id, "running")
        self._emit(
            QueueEvent(
                event_type=EventType.JOB_STARTED,
                batch_id=batch_id,
                job_id=job_id,
                src_path=src_str,
                dst_fmt=dst_fmt,
                timestamp=time.time(),
            )
        )

        def on_progress(pct: float | None, msg: str = "") -> None:
            self._emit(
                QueueEvent(
                    event_type=EventType.JOB_PROGRESS,
                    batch_id=batch_id,
                    job_id=job_id,
                    src_path=src_str,
                    dst_fmt=dst_fmt,
                    percent=pct,
                    message=msg,
                    timestamp=time.time(),
                )
            )

        try:
            res = convert(
                src_path,
                dst_fmt,
                out_dir=out_dir,
                on_progress=on_progress,
                cancel=cancel_token,
                registry=self._registry,
            )

            q_val = res.quality.value if hasattr(res.quality, "value") else str(res.quality)
            self._finish_job(
                job_id=job_id,
                batch_id=batch_id,
                src_path=src_str,
                dst_fmt=dst_fmt,
                status="success",
                output_path=str(res.output),
                quality=q_val,
                warnings=list(res.warnings),
            )

        except CuttleError as ce:
            if ce.code == "E_CANCELLED" or cancel_token.cancelled:
                self._finish_job(
                    job_id=job_id,
                    batch_id=batch_id,
                    src_path=src_str,
                    dst_fmt=dst_fmt,
                    status="cancelled",
                    error_code="E_CANCELLED",
                    error_msg=ce.user_message,
                )
            else:
                self._finish_job(
                    job_id=job_id,
                    batch_id=batch_id,
                    src_path=src_str,
                    dst_fmt=dst_fmt,
                    status="failed",
                    error_code=ce.code,
                    error_msg=ce.user_message,
                )

        except Exception as ex:
            if cancel_token.cancelled:
                self._finish_job(
                    job_id=job_id,
                    batch_id=batch_id,
                    src_path=src_str,
                    dst_fmt=dst_fmt,
                    status="cancelled",
                    error_code="E_CANCELLED",
                    error_msg="Cancelled by user",
                )
            else:
                self._finish_job(
                    job_id=job_id,
                    batch_id=batch_id,
                    src_path=src_str,
                    dst_fmt=dst_fmt,
                    status="failed",
                    error_code="E_TOOL_FAILED",
                    error_msg=str(ex),
                )

    def _finish_job(
        self,
        *,
        job_id: str,
        batch_id: str,
        src_path: str,
        dst_fmt: str,
        status: str,
        output_path: str | None = None,
        quality: str | None = None,
        warnings: list[str] | None = None,
        error_code: str | None = None,
        error_msg: str | None = None,
    ) -> None:
        """Record final state in DB, emit JOB_DONE, and check for batch completion."""
        # 1. Update SQLite DB
        self._db.update_state(
            job_id,
            status,
            output_path=output_path,
            quality=quality,
            warnings=warnings,
            error_code=error_code,
            error_msg=error_msg,
        )

        # 2. Emit JOB_DONE event
        self._emit(
            QueueEvent(
                event_type=EventType.JOB_DONE,
                batch_id=batch_id,
                job_id=job_id,
                src_path=src_path,
                dst_fmt=dst_fmt,
                status=status,
                output_path=output_path,
                quality=quality,
                error_code=error_code,
                error_msg=error_msg,
                timestamp=time.time(),
            )
        )

        # 3. Update BatchTracker and check for BATCH_DONE
        batch_done_event: QueueEvent | None = None
        with self._lock:
            self._tokens.pop(job_id, None)
            self._futures.pop(job_id, None)

            tracker = self._batch_trackers.get(batch_id)
            if tracker is not None:
                if status == "success":
                    tracker.succeeded += 1
                elif status == "cancelled":
                    tracker.cancelled += 1
                else:
                    tracker.failed += 1

                if tracker.is_complete:
                    batch_done_event = QueueEvent(
                        event_type=EventType.BATCH_DONE,
                        batch_id=batch_id,
                        job_id=None,
                        timestamp=time.time(),
                        total=tracker.total,
                        succeeded=tracker.succeeded,
                        failed=tracker.failed,
                        cancelled=tracker.cancelled,
                    )
                    self._batch_trackers.pop(batch_id, None)

        if batch_done_event is not None:
            self._emit(batch_done_event)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a specific job if it is currently queued or running."""
        with self._lock:
            token = self._tokens.get(job_id)
            if token is None:
                return False
            token.cancel()
            return True

    def cancel_batch(self, batch_id: str) -> int:
        """Cancel all queued and running jobs belonging to a batch."""
        with self._lock:
            tracker = self._batch_trackers.get(batch_id)
            if tracker is None:
                return 0
            job_ids = list(tracker.job_ids)
            tokens = [self._tokens[jid] for jid in job_ids if jid in self._tokens]

        count = 0
        for token in tokens:
            token.cancel()
            count += 1
        return count

    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        """Shut down the background executor."""
        with self._lock:
            self._is_shutdown = True
            if cancel_pending:
                for token in self._tokens.values():
                    token.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=cancel_pending)

    def __enter__(self) -> JobQueue:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.shutdown(wait=True, cancel_pending=True)
