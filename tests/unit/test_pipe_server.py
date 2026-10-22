"""Unit tests for cuttle/worker/pipe_server.py Named Pipe server and 300ms batcher.

Per task card P2-04:
- Verifies ping/pong IPC over Windows Named Pipe.
- Verifies 300ms Multi-Select Batching merging rapid consecutive convert commands into 1 batch.
- Verifies discrete requests separated by time creating distinct batches.
- Verifies job and batch cancellation relay over pipe.
- Verifies graceful handling of malformed or invalid JSON payloads.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import pytest

from cuttle.platform.windows.pipe import call_pipe, get_default_pipe_name
from cuttle.worker.db import JobDatabase
from cuttle.worker.pipe_server import PipeServer
from cuttle.worker.queue import JobQueue

is_win = sys.platform == "win32"
pytestmark = pytest.mark.skipif(not is_win, reason="Named Pipes require Windows")


@pytest.fixture
def test_pipe_name() -> str:
    unique_id = uuid.uuid4().hex[:8]
    return rf"\\.\pipe\cuttle-test-{unique_id}"


@pytest.fixture
def pipe_fixture(tmp_path: Path, test_pipe_name: str) -> tuple[PipeServer, JobQueue, JobDatabase]:
    db = JobDatabase(tmp_path / "test_pipe.db")
    queue = JobQueue(db, max_workers=2)
    server = PipeServer(queue, pipe_name=test_pipe_name, debounce_s=0.15)
    server.start()
    yield server, queue, db
    server.stop()
    queue.shutdown(wait=True, cancel_pending=True)
    db.close()


def test_default_pipe_name() -> None:
    name = get_default_pipe_name()
    assert name.startswith(r"\\.\pipe\cuttle-")


def test_ping_pong(pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase]) -> None:
    server, _, _ = pipe_fixture
    req = json.dumps({"op": "ping"}).encode("utf-8")
    resp_raw = call_pipe(server.pipe_name, req)
    resp = json.loads(resp_raw.decode("utf-8"))
    assert resp["status"] == "ok"
    assert resp["message"] == "pong"


def test_multi_select_batching(
    pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase],
    fixtures_dir: Path,
) -> None:
    server, _queue, db = pipe_fixture

    # Simulate 4 files selected in Explorer: fired 20ms apart
    files = ["img.png", "img.jpg", "img.bmp", "img.webp"]
    batch_ids: list[str] = []

    for fname in files:
        src = str(fixtures_dir / fname)
        req = json.dumps({"op": "convert", "src": src, "dst": "png"}).encode("utf-8")
        resp_raw = call_pipe(server.pipe_name, req)
        resp = json.loads(resp_raw.decode("utf-8"))
        assert resp["status"] == "queued"
        batch_ids.append(resp["batch_id"])
        time.sleep(0.02)

    # All 4 rapid calls must have received the EXACT SAME batch_id
    assert len(set(batch_ids)) == 1
    common_batch_id = batch_ids[0]

    # Wait for the 150ms debounce timer to fire and submit to queue
    time.sleep(0.3)

    # Verify that all 4 jobs were recorded in SQLite under that batch_id
    batch_jobs = db.list_jobs(batch_id=common_batch_id)
    assert len(batch_jobs) == 4
    assert {j.src_path for j in batch_jobs} == {str(fixtures_dir / f) for f in files}


def test_discrete_requests_create_different_batches(
    pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase],
    fixtures_dir: Path,
) -> None:
    server, _queue, _db = pipe_fixture

    # Request 1
    src1 = str(fixtures_dir / "img.png")
    req1 = json.dumps({"op": "convert", "src": src1, "dst": "jpg"}).encode("utf-8")
    resp1 = json.loads(call_pipe(server.pipe_name, req1).decode("utf-8"))
    b1 = resp1["batch_id"]

    # Wait longer than debounce window (150ms)
    time.sleep(0.25)

    # Request 2
    src2 = str(fixtures_dir / "img.jpg")
    req2 = json.dumps({"op": "convert", "src": src2, "dst": "png"}).encode("utf-8")
    resp2 = json.loads(call_pipe(server.pipe_name, req2).decode("utf-8"))
    b2 = resp2["batch_id"]

    assert b1 != b2


def test_cancellation_over_pipe(
    pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase],
) -> None:
    server, _queue, _db = pipe_fixture

    # Cancel non-existent job
    req_job = json.dumps({"op": "cancel_job", "job_id": "nonexistent"}).encode("utf-8")
    resp_job = json.loads(call_pipe(server.pipe_name, req_job).decode("utf-8"))
    assert resp_job["status"] == "ok"
    assert resp_job["cancelled"] is False

    # Cancel non-existent batch
    req_batch = json.dumps({"op": "cancel_batch", "batch_id": "nonexistent"}).encode("utf-8")
    resp_batch = json.loads(call_pipe(server.pipe_name, req_batch).decode("utf-8"))
    assert resp_batch["status"] == "ok"
    assert resp_batch["cancelled_count"] == 0


def test_error_handling_malformed_and_unknown(
    pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase],
) -> None:
    server, _, _ = pipe_fixture

    # 1. Invalid JSON string
    resp1 = json.loads(call_pipe(server.pipe_name, b"not valid json").decode("utf-8"))
    assert resp1["status"] == "error"

    # 2. Unknown operation
    req2 = json.dumps({"op": "teleport"}).encode("utf-8")
    resp2 = json.loads(call_pipe(server.pipe_name, req2).decode("utf-8"))
    assert resp2["status"] == "error"
    assert "teleport" in resp2["message"]

    # 3. Convert missing fields
    req3 = json.dumps({"op": "convert", "src": "file.mp4"}).encode("utf-8")
    resp3 = json.loads(call_pipe(server.pipe_name, req3).decode("utf-8"))
    assert resp3["status"] == "error"
    assert "requires 'src' and 'dst'" in resp3["message"]


def test_concurrent_burst_pipe_requests(
    pipe_fixture: tuple[PipeServer, JobQueue, JobDatabase],
    fixtures_dir: Path,
) -> None:
    """8 concurrent clients hitting the pipe simultaneously must all succeed without drops."""
    import concurrent.futures

    server, _, _db = pipe_fixture
    files = ["img.png", "img.jpg", "img.bmp", "img.webp"] * 2  # 8 files
    results: list[dict[str, str]] = []

    def _send(fname: str) -> dict[str, str]:
        src = str(fixtures_dir / fname)
        req = json.dumps({"op": "convert", "src": src, "dst": "png"}).encode("utf-8")
        resp_raw = call_pipe(server.pipe_name, req, timeout_ms=5000)
        res: dict[str, str] = json.loads(resp_raw.decode("utf-8"))
        return res

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(_send, f) for f in files]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    assert len(results) == 8
    for r in results:
        assert r["status"] == "queued"
        assert "batch_id" in r
