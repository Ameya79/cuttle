"""Unit tests for cuttle/ui/progress_window.py PySide6 floating progress window.

Per task card P2-06:
- Runs headlessly using QT_QPA_PLATFORM=offscreen.
- Verifies window initialization, styling, and bottom-right positioning.
- Verifies dynamic addition of job rows.
- Verifies live progress event handling.
- Verifies completion states (success, failed, cancelled).
- Verifies cancellation signal emission.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt

from cuttle.ui.progress_window import FloatingProgressWindow, get_or_create_app
from cuttle.worker.queue import EventType, QueueEvent

# Force headless offscreen platform for tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_window_initialization() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="test-batch", auto_close_ms=0)
    try:
        assert win.width() == 340
        flags = win.windowFlags()
        assert Qt.WindowType.FramelessWindowHint in flags
        assert Qt.WindowType.WindowStaysOnTopHint in flags
        assert win.lbl_header.text() == "Cuttle Converting"
        assert not win.btn_cancel_all.isHidden()
    finally:
        win.close()


def test_add_job_rows_and_header_counter() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="test-batch", auto_close_ms=0)
    try:
        r1 = win.add_job("j1", "video.mp4", "mp3")
        assert r1.job_id == "j1"
        assert "video.mp4 ➔ MP3" in r1.lbl_title.text()
        assert win.lbl_header.text() == "Cuttle Converting (1)"

        r2 = win.add_job("j2", "photo.png", "jpg")
        assert r2.job_id == "j2"
        assert win.lbl_header.text() == "Cuttle Converting (2)"
    finally:
        win.close()


def test_progress_event_updates() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="test-batch", auto_close_ms=0)
    try:
        win.add_job("j1", "audio.wav", "mp3")
        row = win._rows["j1"]

        # 1. Started event
        win.handle_event(
            QueueEvent(
                event_type=EventType.JOB_STARTED,
                batch_id="test-batch",
                job_id="j1",
            )
        )
        assert "Converting" in row.lbl_status.text()

        # 2. Progress event
        win.handle_event(
            QueueEvent(
                event_type=EventType.JOB_PROGRESS,
                batch_id="test-batch",
                job_id="j1",
                percent=68.5,
                message="encoding",
            )
        )
        assert row.progress_bar.value() == 68
        assert "68%" in row.lbl_status.text()
        assert "encoding" in row.lbl_status.text()
    finally:
        win.close()


def test_job_completion_states() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="test-batch", auto_close_ms=0)
    try:
        win.add_job("j_succ", "1.mp4", "mp3")
        win.add_job("j_fail", "2.mp4", "mp3")
        win.add_job("j_canc", "3.mp4", "mp3")

        # Success
        win.handle_event(
            QueueEvent(
                event_type=EventType.JOB_DONE,
                batch_id="test-batch",
                job_id="j_succ",
                status="success",
            )
        )
        r_succ = win._rows["j_succ"]
        assert r_succ.progress_bar.value() == 100
        assert "Ready" in r_succ.lbl_status.text()

        # Failed
        win.handle_event(
            QueueEvent(
                event_type=EventType.JOB_DONE,
                batch_id="test-batch",
                job_id="j_fail",
                status="failed",
                error_msg="Encoder error",
            )
        )
        r_fail = win._rows["j_fail"]
        assert "Encoder error" in r_fail.lbl_status.text()

        # Cancelled
        win.handle_event(
            QueueEvent(
                event_type=EventType.JOB_DONE,
                batch_id="test-batch",
                job_id="j_canc",
                status="cancelled",
            )
        )
        r_canc = win._rows["j_canc"]
        assert "Cancelled" in r_canc.lbl_status.text()
    finally:
        win.close()


def test_cancel_signals_emitted() -> None:
    _ = get_or_create_app()
    cancelled_jobs: list[str] = []
    cancelled_batches: list[str] = []

    win = FloatingProgressWindow(
        batch_id="batch-xyz",
        on_cancel_job=cancelled_jobs.append,
        on_cancel_batch=cancelled_batches.append,
        auto_close_ms=0,
    )
    try:
        win.add_job("job-abc", "sample.mp4", "mp3")
        row = win._rows["job-abc"]

        # Click individual cancel button
        row.btn_cancel.click()
        assert cancelled_jobs == ["job-abc"]

        # Click cancel all button
        win.btn_cancel_all.click()
        assert cancelled_batches == ["batch-xyz"]
        assert not win.btn_cancel_all.isEnabled()
    finally:
        win.close()


def test_batch_done_event() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="batch-done-test", auto_close_ms=0)
    try:
        win.add_job("j1", "1.png", "jpg")
        win.add_job("j2", "2.png", "jpg")

        win.handle_event(
            QueueEvent(
                event_type=EventType.BATCH_DONE,
                batch_id="batch-done-test",
                job_id=None,
                total=2,
                succeeded=2,
                failed=0,
            )
        )
        assert "Completed (2/2)" in win.lbl_header.text()
        assert not win.btn_cancel_all.isVisible()
    finally:
        win.close()


def test_bottom_right_positioning() -> None:
    _ = get_or_create_app()
    win = FloatingProgressWindow(batch_id="pos-test", auto_close_ms=0)
    try:
        win.add_job("j1", "a.mp4", "mp3")
        win.position_bottom_right()
        pos = win.pos()
        assert pos.x() >= 0
        assert pos.y() >= 0
    finally:
        win.close()
