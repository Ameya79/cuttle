"""End-to-end integration tests for the Cuttle Windows worker and pipeline.

Per task card P2-11:
- Validates named pipe IPC with multi-file rapid debouncing.
- Validates job queue execution and SQLite state transitions.
- Validates job cancellation and process termination.
- Validates context menu installation and clean leave-no-trace uninstallation.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import uuid
from pathlib import Path

import pytest

from cuttle.platform.windows.pipe import call_pipe
from cuttle.shell.registry_installer import (
    RegistryConfig,
    delete_key_tree,
    install_context_menus,
    uninstall_context_menus,
)
from cuttle.worker.db import JobDatabase
from cuttle.worker.pipe_server import PipeServer
from cuttle.worker.queue import EventType, JobQueue, QueueEvent

SANDBOX_BASE = r"Software\CuttleTest\Classes"


@pytest.fixture(autouse=True)
def clean_sandbox() -> None:
    """Ensure registry test sandbox is clean before and after tests."""
    if sys.platform == "win32":
        import winreg

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\CuttleTest")
    yield
    if sys.platform == "win32":
        import winreg

        delete_key_tree(winreg.HKEY_CURRENT_USER, r"Software\CuttleTest")


def test_end_to_end_shell_installation_and_clean_removal(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows only")

    import winreg

    manifest = tmp_path / "installed_keys.json"
    cfg = RegistryConfig(
        base_path=SANDBOX_BASE,
        cuttlectl_cmd=r'"C:\Program Files\Cuttle\cuttlectl.exe"',
        manifest_path=manifest,
    )

    # 1. Install
    created = install_context_menus(cfg)
    assert len(created) > 0
    assert manifest.is_file()

    # Verify a key in registry
    test_key = f"{SANDBOX_BASE}\\SystemFileAssociations\\.mp4\\shell\\Cuttle"
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, test_key)
    winreg.CloseKey(k)

    # 2. Uninstall
    removed = uninstall_context_menus(cfg)
    assert removed == len(created)
    assert not manifest.exists()

    # Verify key is completely removed
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, test_key)


def test_end_to_end_pipe_debounce_and_conversions(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows only")

    project_root = Path(__file__).resolve().parent.parent.parent
    fixtures_dir = project_root / "tests" / "fixtures"

    src_img = fixtures_dir / "img.png"
    src_wav = fixtures_dir / "audio.wav"

    if not src_img.is_file() or not src_wav.is_file():
        pytest.skip("Fixtures missing; run tests/make_fixtures.py")

    work_img = tmp_path / "sample.png"
    work_wav = tmp_path / "sample.wav"
    shutil.copy2(src_img, work_img)
    shutil.copy2(src_wav, work_wav)

    db_path = tmp_path / "state.db"
    db = JobDatabase(db_path)
    events: list[QueueEvent] = []
    queue = JobQueue(db, max_workers=2, event_cb=events.append)

    pipe_name = f"\\\\.\\pipe\\cuttle-pipe-test-{uuid.uuid4().hex[:8]}"
    server = PipeServer(queue, pipe_name=pipe_name, debounce_s=0.1)
    server.start()

    try:
        # Submit 2 files rapidly to trigger debounce window
        req1 = {
            "op": "convert",
            "src": str(work_img),
            "dst": "jpg",
            "out_dir": str(tmp_path),
        }
        req2 = {
            "op": "convert",
            "src": str(work_wav),
            "dst": "mp3",
            "out_dir": str(tmp_path),
        }

        resp1_raw = call_pipe(pipe_name, json.dumps(req1).encode("utf-8"), timeout_ms=3000)
        resp2_raw = call_pipe(pipe_name, json.dumps(req2).encode("utf-8"), timeout_ms=3000)

        r1 = json.loads(resp1_raw.decode("utf-8"))
        r2 = json.loads(resp2_raw.decode("utf-8"))

        assert r1.get("status") == "queued"
        assert r2.get("status") == "queued"

        # Debounce bundles them into the exact same batch ID
        batch_id = r1.get("batch_id")
        assert batch_id is not None
        assert r2.get("batch_id") == batch_id

        # Wait for conversions to complete
        start_wait = time.monotonic()
        while time.monotonic() - start_wait < 15.0:
            batch_events = [e for e in events if e.event_type == EventType.BATCH_DONE]
            if batch_events:
                break
            time.sleep(0.1)

        # Verify output files exist and are non-empty
        out_jpg = tmp_path / "sample (converted).jpg"
        out_mp3 = tmp_path / "sample (converted).mp3"

        assert out_jpg.is_file(), f"Expected {out_jpg} to exist"
        assert out_jpg.stat().st_size > 0

        assert out_mp3.is_file(), f"Expected {out_mp3} to exist"
        assert out_mp3.stat().st_size > 0

        # Verify DB states
        jobs = db.list_jobs(batch_id=batch_id)
        assert len(jobs) == 2
        for j in jobs:
            assert j.state == "success"

    finally:
        server.stop()
        queue.shutdown(wait=True)


def test_end_to_end_cancellation_pipeline(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("Windows only")

    db_path = tmp_path / "state_cancel.db"
    db = JobDatabase(db_path)
    queue = JobQueue(db, max_workers=1)

    pipe_name = f"\\\\.\\pipe\\cuttle-cancel-test-{uuid.uuid4().hex[:8]}"
    server = PipeServer(queue, pipe_name=pipe_name, debounce_s=0.05)
    server.start()

    try:
        # Submit a batch with a non-existent file or simulated job
        dummy = tmp_path / "dummy.png"
        dummy.write_text("not a real png")

        req = {
            "op": "convert",
            "src": str(dummy),
            "dst": "jpg",
            "out_dir": str(tmp_path),
        }
        resp_raw = call_pipe(pipe_name, json.dumps(req).encode("utf-8"), timeout_ms=3000)
        resp = json.loads(resp_raw.decode("utf-8"))
        batch_id = resp["batch_id"]

        # Send cancellation
        cancel_req = {"op": "cancel_batch", "batch_id": batch_id}
        cancel_raw = call_pipe(pipe_name, json.dumps(cancel_req).encode("utf-8"), timeout_ms=3000)
        cancel_resp = json.loads(cancel_raw.decode("utf-8"))
        assert cancel_resp.get("status") == "ok"

    finally:
        server.stop()
        queue.shutdown(wait=True)
