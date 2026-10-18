"""Unit tests for cuttle/worker/cuttlectl.py fast launcher CLI.

Per task card P2-05:
- Verifies ping command with running worker.
- Verifies submit command with single and multiple files.
- Verifies cancel command by job_id and batch_id.
- Verifies error handling when files do not exist or arguments are missing.
- Verifies ensure_worker_running auto-start mechanism.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

from cuttle.platform.windows.pipe import call_pipe
from cuttle.worker.cuttlectl import ensure_worker_running
from cuttle.worker.cuttlectl import main as cuttlectl_main
from cuttle.worker.db import JobDatabase
from cuttle.worker.pipe_server import PipeServer
from cuttle.worker.queue import JobQueue

is_win = sys.platform == "win32"
pytestmark = pytest.mark.skipif(not is_win, reason="Named Pipes require Windows")


@pytest.fixture
def test_pipe_name() -> str:
    return rf"\\.\pipe\cuttle-ctl-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def running_worker(
    tmp_path: Path,
    test_pipe_name: str,
) -> tuple[PipeServer, JobQueue, JobDatabase, str]:
    db = JobDatabase(tmp_path / "ctl_test.db")
    queue = JobQueue(db, max_workers=2)
    server = PipeServer(queue, pipe_name=test_pipe_name, debounce_s=0.1)
    server.start()
    yield server, queue, db, test_pipe_name
    server.stop()
    queue.shutdown(wait=True, cancel_pending=True)
    db.close()


def test_cuttlectl_ping(
    running_worker: tuple[PipeServer, JobQueue, JobDatabase, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, _, pipe_name = running_worker
    exit_code = cuttlectl_main(["--pipe", pipe_name, "ping"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "active (pong)" in captured.out


def test_cuttlectl_submit_single_file(
    running_worker: tuple[PipeServer, JobQueue, JobDatabase, str],
    fixtures_dir: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, db, pipe_name = running_worker
    src = fixtures_dir / "img.png"
    out_dir = tmp_path / "out"

    exit_code = cuttlectl_main(
        [
            "--pipe",
            pipe_name,
            "submit",
            "--to",
            "jpg",
            "--out-dir",
            str(out_dir),
            str(src),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Submitted 1 file(s)" in captured.out

    time.sleep(0.3)
    jobs = db.list_jobs()
    assert len(jobs) >= 1
    assert any(j.dst_fmt == "jpg" for j in jobs)


def test_cuttlectl_submit_multi_files(
    running_worker: tuple[PipeServer, JobQueue, JobDatabase, str],
    fixtures_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, db, pipe_name = running_worker
    src1 = fixtures_dir / "img.png"
    src2 = fixtures_dir / "img.jpg"

    exit_code = cuttlectl_main(
        [
            "--pipe",
            pipe_name,
            "submit",
            "--to",
            "bmp",
            str(src1),
            str(src2),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Submitted 2 file(s)" in captured.out

    time.sleep(0.3)
    jobs = db.list_jobs()
    assert len(jobs) >= 2


def test_cuttlectl_cancel_commands(
    running_worker: tuple[PipeServer, JobQueue, JobDatabase, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, _, pipe_name = running_worker

    # Cancel job
    code_job = cuttlectl_main(["--pipe", pipe_name, "cancel", "--job", "job-nonexistent"])
    assert code_job == 0
    out_job = capsys.readouterr().out
    assert "Cancellation dispatched" in out_job

    # Cancel batch
    code_batch = cuttlectl_main(["--pipe", pipe_name, "cancel", "--batch", "batch-nonexistent"])
    assert code_batch == 0
    out_batch = capsys.readouterr().out
    assert "Cancellation dispatched" in out_batch

    # Cancel without flags
    code_err = cuttlectl_main(["--pipe", pipe_name, "cancel"])
    assert code_err == 1


def test_cuttlectl_missing_file_returns_error(
    running_worker: tuple[PipeServer, JobQueue, JobDatabase, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, _, _, pipe_name = running_worker
    exit_code = cuttlectl_main(
        [
            "--pipe",
            pipe_name,
            "submit",
            "--to",
            "mp3",
            "this_file_does_not_exist_anywhere.mov",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "do not exist" in err


def test_cuttlectl_auto_start_worker() -> None:
    auto_pipe = rf"\\.\pipe\cuttle-autostart-test-{uuid.uuid4().hex[:8]}"

    try:
        pipe_connected = ensure_worker_running(pipe_name=auto_pipe, timeout_s=4.0)
        assert pipe_connected == auto_pipe

        # Send ping to verify it is responsive
        resp = call_pipe(auto_pipe, b'{"op": "ping"}', timeout_ms=1000)
        assert b"pong" in resp

        # Send shutdown to stop the auto-started worker
        call_pipe(auto_pipe, b'{"op": "shutdown"}', timeout_ms=1000)
    finally:
        time.sleep(0.2)
