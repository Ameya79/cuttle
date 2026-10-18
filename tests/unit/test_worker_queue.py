"""Unit tests for cuttle/worker/queue.py concurrency controller and event streamer.

Per task card P2-03:
- Verifies concurrency cap throttling (max_workers).
- Verifies lifecycle events: JOB_QUEUED -> JOB_STARTED -> JOB_PROGRESS -> JOB_DONE -> BATCH_DONE.
- Verifies individual job cancellation.
- Verifies entire batch cancellation.
- Verifies isolated failure handling (one failure does not break the batch).
- Verifies state persistence in SQLite JobDatabase.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from cuttle.worker.db import JobDatabase
from cuttle.worker.queue import EventType, JobQueue, QueueEvent


@pytest.fixture
def queue_env(tmp_path: Path) -> tuple[JobDatabase, Path]:
    """Fixture providing an isolated JobDatabase and output directory."""
    db_file = tmp_path / "test_queue.db"
    db = JobDatabase(db_file)
    out_dir = tmp_path / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return db, out_dir


class TestJobQueueBasics:
    def test_default_and_custom_max_workers(self, queue_env: tuple[JobDatabase, Path]) -> None:
        db, _ = queue_env
        q_default = JobQueue(db)
        assert q_default.max_workers >= 1
        q_default.shutdown()

        q_custom = JobQueue(db, max_workers=3)
        assert q_custom.max_workers == 3
        q_custom.shutdown()

    def test_submit_to_shutdown_queue_raises(self, queue_env: tuple[JobDatabase, Path]) -> None:
        db, _ = queue_env
        q = JobQueue(db, max_workers=1)
        q.shutdown()
        with pytest.raises(RuntimeError, match="shutdown"):
            q.submit_job("b1", Path("test.png"), "jpg")

    def test_submit_empty_batch_returns_empty(self, queue_env: tuple[JobDatabase, Path]) -> None:
        db, _ = queue_env
        with JobQueue(db, max_workers=1) as q:
            result = q.submit_batch("b1", [])
            assert result == []


class TestJobLifecycleAndEvents:
    def test_single_job_success_lifecycle(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        events: list[QueueEvent] = []

        with JobQueue(db, max_workers=2, event_cb=events.append) as q:
            src = fixtures_dir / "img.png"
            job_id = q.submit_job("batch-1", src, "jpg", out_dir=out_dir)

            # Wait for batch completion
            for _ in range(50):
                if any(e.event_type == EventType.BATCH_DONE for e in events):
                    break
                time.sleep(0.05)

        event_types = [e.event_type for e in events]
        assert EventType.JOB_QUEUED in event_types
        assert EventType.JOB_STARTED in event_types
        assert EventType.JOB_DONE in event_types
        assert EventType.BATCH_DONE in event_types

        # Verify final job state in DB
        rec = db.get_job(job_id)
        assert rec is not None
        assert rec.state == "success"
        assert rec.output_path is not None
        assert Path(rec.output_path).exists()

        # Check BATCH_DONE payload
        batch_event = next(e for e in events if e.event_type == EventType.BATCH_DONE)
        assert batch_event.batch_id == "batch-1"
        assert batch_event.total == 1
        assert batch_event.succeeded == 1
        assert batch_event.failed == 0
        assert batch_event.cancelled == 0

    def test_batch_success_lifecycle(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        events: list[QueueEvent] = []

        items = [
            (fixtures_dir / "img.png", "bmp"),
            (fixtures_dir / "img.jpg", "png"),
            (fixtures_dir / "img.bmp", "jpg"),
        ]

        with JobQueue(db, max_workers=2, event_cb=events.append) as q:
            job_ids = q.submit_batch("batch-multi", items, out_dir=out_dir)
            assert len(job_ids) == 3

            for _ in range(100):
                if any(e.event_type == EventType.BATCH_DONE for e in events):
                    break
                time.sleep(0.05)

        batch_done = next((e for e in events if e.event_type == EventType.BATCH_DONE), None)
        assert batch_done is not None
        assert batch_done.total == 3
        assert batch_done.succeeded == 3
        assert batch_done.failed == 0

        # All jobs succeeded in DB
        for jid in job_ids:
            r = db.get_job(jid)
            assert r is not None
            assert r.state == "success"


class TestConcurrencyAndCancellation:
    def test_concurrency_cap_limits_simultaneous_workers(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        active_counts: list[int] = []
        lock = threading.Lock()
        current_active = 0

        def on_event(e: QueueEvent) -> None:
            nonlocal current_active
            with lock:
                if e.event_type == EventType.JOB_STARTED:
                    current_active += 1
                    active_counts.append(current_active)
                elif e.event_type == EventType.JOB_DONE:
                    current_active -= 1

        # Max 2 workers
        with JobQueue(db, max_workers=2, event_cb=on_event) as q:
            items = [
                (fixtures_dir / "img.png", "jpg"),
                (fixtures_dir / "img.png", "bmp"),
                (fixtures_dir / "img.jpg", "png"),
                (fixtures_dir / "img.bmp", "jpg"),
            ]
            q.submit_batch("batch-throttle", items, out_dir=out_dir)

            for _ in range(100):
                with lock:
                    if len(active_counts) == len(items) and current_active == 0:
                        break
                time.sleep(0.05)

        # Active worker count must never exceed 2
        assert len(active_counts) > 0
        assert max(active_counts) <= 2

    def test_cancel_individual_job(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        events: list[QueueEvent] = []

        with JobQueue(db, max_workers=1, event_cb=events.append) as q:
            # Video to webm takes enough time to reliably cancel
            src = fixtures_dir / "video.mp4"
            job_id = q.submit_job("batch-cancel-single", src, "webm", out_dir=out_dir)

            # Cancel immediately
            cancelled = q.cancel_job(job_id)
            assert cancelled is True

            for _ in range(100):
                if any(e.event_type == EventType.BATCH_DONE for e in events):
                    break
                time.sleep(0.05)

        done_event = next(
            (e for e in events if e.event_type == EventType.JOB_DONE and e.job_id == job_id),
            None,
        )
        assert done_event is not None
        assert done_event.status == "cancelled"

        rec = db.get_job(job_id)
        assert rec is not None
        assert rec.state == "cancelled"

    def test_cancel_entire_batch(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        events: list[QueueEvent] = []

        # 1 worker so jobs 2, 3, 4 are queued
        with JobQueue(db, max_workers=1, event_cb=events.append) as q:
            items = [
                (fixtures_dir / "video.mp4", "webm"),
                (fixtures_dir / "img.png", "jpg"),
                (fixtures_dir / "img.jpg", "png"),
            ]
            job_ids = q.submit_batch("batch-cancel-all", items, out_dir=out_dir)

            count = q.cancel_batch("batch-cancel-all")
            assert count >= 1

            for _ in range(100):
                if any(e.event_type == EventType.BATCH_DONE for e in events):
                    break
                time.sleep(0.05)

        # Batch summary must report cancellations
        batch_event = next(e for e in events if e.event_type == EventType.BATCH_DONE)
        assert batch_event.cancelled >= 1

        # At least one job is cancelled in DB
        states = [db.get_job(jid).state for jid in job_ids if db.get_job(jid) is not None]
        assert "cancelled" in states


class TestFailureIsolation:
    def test_isolated_failure_does_not_abort_batch(
        self,
        queue_env: tuple[JobDatabase, Path],
        fixtures_dir: Path,
    ) -> None:
        db, out_dir = queue_env
        events: list[QueueEvent] = []

        with JobQueue(db, max_workers=2, event_cb=events.append) as q:
            # File 1 does not exist -> fails with E_SRC_MISSING
            missing_file = fixtures_dir / "does_not_exist.mp4"
            # File 2 is valid -> succeeds
            valid_file = fixtures_dir / "img.png"

            q.submit_batch(
                "batch-fail-iso",
                [(missing_file, "mp3"), (valid_file, "jpg")],
                out_dir=out_dir,
            )

            for _ in range(100):
                if any(e.event_type == EventType.BATCH_DONE for e in events):
                    break
                time.sleep(0.05)

        batch_event = next(e for e in events if e.event_type == EventType.BATCH_DONE)
        assert batch_event.total == 2
        assert batch_event.succeeded == 1
        assert batch_event.failed == 1

        # Missing file job must be marked failed with E_SRC_MISSING
        done_events = [e for e in events if e.event_type == EventType.JOB_DONE]
        failed_event = next(e for e in done_events if e.status == "failed")
        assert failed_event.error_code == "E_SRC_MISSING"

        success_event = next(e for e in done_events if e.status == "success")
        assert success_event.output_path is not None
        assert Path(success_event.output_path).exists()
