"""Unit tests for cuttle/worker/db.py SQLite state database.

Per task card P2-02:
- Verifies database initialization, table creation, indices, and WAL mode.
- Verifies full job lifecycle transitions: queued -> running -> validating -> success.
- Verifies failure and cancellation transitions.
- Verifies startup crash recovery resetting 'running' and 'validating' jobs to 'failed'.
- Verifies batch and state query filters.
- Verifies concurrent multi-threaded safety.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path

import pytest

from cuttle.worker.db import JobDatabase, get_default_db_path


@pytest.fixture
def db(tmp_path: Path) -> JobDatabase:
    """Fixture providing an isolated JobDatabase instance in a temp directory."""
    db_file = tmp_path / "test_state.db"
    database = JobDatabase(db_file)
    yield database
    database.close()


class TestJobDatabaseInitialization:
    def test_schema_and_indices_created(self, db: JobDatabase) -> None:
        with db._lock:
            cursor = db._conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
            assert cursor.fetchone() is not None

            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            index_names = {row[0] for row in cursor.fetchall()}
            assert "idx_jobs_batch_id" in index_names
            assert "idx_jobs_state" in index_names

    def test_default_path_resolution(self) -> None:
        path = get_default_db_path()
        assert isinstance(path, Path)
        assert path.name == "state.db"
        assert "Cuttle" in str(path)


class TestJobLifecycle:
    def test_insert_and_get_job(self, db: JobDatabase) -> None:
        job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        src = "C:/media/video.mp4"
        dst = "mp3"

        rec = db.insert_job(job_id, batch_id, src, dst)
        assert rec.id == job_id
        assert rec.batch_id == batch_id
        assert rec.src_path == src
        assert rec.dst_fmt == "mp3"
        assert rec.state == "queued"
        assert rec.output_path is None
        assert rec.quality is None
        assert rec.error_code is None
        assert rec.error_msg is None
        assert rec.warnings == []
        assert rec.created_at > 0
        assert rec.updated_at >= rec.created_at

        fetched = db.get_job(job_id)
        assert fetched == rec

    def test_get_nonexistent_returns_none(self, db: JobDatabase) -> None:
        assert db.get_job("nonexistent-id") is None

    def test_state_transitions_to_success(self, db: JobDatabase) -> None:
        job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        db.insert_job(job_id, batch_id, "file.wav", "mp3")

        # 1. Move to running
        r1 = db.update_state(job_id, "running")
        assert r1 is not None
        assert r1.state == "running"

        # 2. Move to validating
        r2 = db.update_state(job_id, "validating")
        assert r2 is not None
        assert r2.state == "validating"

        # 3. Move to success
        r3 = db.update_state(
            job_id,
            "success",
            output_path="C:/media/file (converted).mp3",
            quality="perceptual",
            warnings=["Audio re-encoded"],
        )
        assert r3 is not None
        assert r3.state == "success"
        assert r3.output_path == "C:/media/file (converted).mp3"
        assert r3.quality == "perceptual"
        assert r3.warnings == ["Audio re-encoded"]
        assert r3.error_code is None

    def test_state_transitions_to_failure(self, db: JobDatabase) -> None:
        job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        db.insert_job(job_id, batch_id, "bad.mp4", "mp3")

        db.update_state(job_id, "running")
        rec = db.update_state(
            job_id,
            "failed",
            error_code="E_TOOL_FAILED",
            error_msg="Encoder crashed with exit code 1",
        )
        assert rec is not None
        assert rec.state == "failed"
        assert rec.error_code == "E_TOOL_FAILED"
        assert rec.error_msg == "Encoder crashed with exit code 1"

    def test_state_transition_to_cancelled(self, db: JobDatabase) -> None:
        job_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        db.insert_job(job_id, batch_id, "long.mov", "mp4")

        rec = db.update_state(
            job_id,
            "cancelled",
            error_code="E_CANCELLED",
            error_msg="User cancelled conversion",
        )
        assert rec is not None
        assert rec.state == "cancelled"
        assert rec.error_code == "E_CANCELLED"

    def test_invalid_state_raises_value_error(self, db: JobDatabase) -> None:
        job_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="Invalid job state"):
            db.insert_job(job_id, "b1", "f.txt", "pdf", state="unknown_state")

        db.insert_job(job_id, "b1", "f.txt", "pdf")
        with pytest.raises(ValueError, match="Invalid job state"):
            db.update_state(job_id, "bogus_state")

    def test_update_nonexistent_job_returns_none(self, db: JobDatabase) -> None:
        assert db.update_state("nonexistent", "running") is None


class TestCrashRecovery:
    def test_startup_crash_recovery(self, db: JobDatabase) -> None:
        b = str(uuid.uuid4())

        # 1. Job left running when process died
        db.insert_job("j1", b, "1.mp4", "mp3")
        db.update_state("j1", "running")

        # 2. Job left validating when process died
        db.insert_job("j2", b, "2.mp4", "mp3")
        db.update_state("j2", "validating")

        # 3. Job still queued
        db.insert_job("j3", b, "3.mp4", "mp3")

        # 4. Job that succeeded cleanly before crash
        db.insert_job("j4", b, "4.mp4", "mp3")
        db.update_state("j4", "success", output_path="4.mp3")

        # Run startup crash recovery
        recovered = db.recover_crashed_jobs()
        assert recovered == 2

        # Check job 1: should be marked failed
        r1 = db.get_job("j1")
        assert r1 is not None
        assert r1.state == "failed"
        assert r1.error_code == "E_TOOL_FAILED"
        assert "terminated unexpectedly" in (r1.error_msg or "")

        # Check job 2: should be marked failed
        r2 = db.get_job("j2")
        assert r2 is not None
        assert r2.state == "failed"
        assert r2.error_code == "E_TOOL_FAILED"

        # Check job 3: should remain queued
        r3 = db.get_job("j3")
        assert r3 is not None
        assert r3.state == "queued"

        # Check job 4: should remain success
        r4 = db.get_job("j4")
        assert r4 is not None
        assert r4.state == "success"


class TestQueryAndListing:
    def test_list_jobs_by_batch_and_state(self, db: JobDatabase) -> None:
        b1 = "batch-alpha"
        b2 = "batch-beta"

        db.insert_job("a1", b1, "a1.mp4", "mp3")
        db.insert_job("a2", b1, "a2.mp4", "mp3")
        db.update_state("a2", "running")

        db.insert_job("b1", b2, "b1.png", "jpg")

        # All jobs
        all_jobs = db.list_jobs()
        assert len(all_jobs) == 3

        # Filter by batch_id
        batch1_jobs = db.list_jobs(batch_id=b1)
        assert len(batch1_jobs) == 2
        assert {j.id for j in batch1_jobs} == {"a1", "a2"}

        # Filter by state
        queued_jobs = db.list_jobs(state="queued")
        assert len(queued_jobs) == 2
        assert {j.id for j in queued_jobs} == {"a1", "b1"}

        # Filter by both
        b1_running = db.list_jobs(batch_id=b1, state="running")
        assert len(b1_running) == 1
        assert b1_running[0].id == "a2"


class TestConcurrency:
    def test_multi_threaded_inserts_and_updates(self, db: JobDatabase) -> None:
        num_threads = 5
        jobs_per_thread = 10
        errors: list[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                batch_id = f"batch-thread-{thread_idx}"
                for i in range(jobs_per_thread):
                    job_id = f"job-{thread_idx}-{i}"
                    db.insert_job(job_id, batch_id, f"src-{i}.mp4", "mp3")
                    db.update_state(job_id, "running")
                    db.update_state(job_id, "success", output_path=f"out-{i}.mp3")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors occurred during concurrent DB access: {errors}"
        total_jobs = db.list_jobs()
        assert len(total_jobs) == num_threads * jobs_per_thread
        assert all(j.state == "success" for j in total_jobs)
