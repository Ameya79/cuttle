"""Cuttle background worker daemon entry point.

Per TRD §6.6:
- Runs startup crash recovery on SQLite state database (marks orphaned jobs failed).
- Starts JobQueue concurrency controller.
- Starts Windows Named Pipe server for right-click IPC.
- Displays System Tray icon and floating progress window on conversion.
- Sends native Windows toast notifications on completion.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

from cuttle.worker.db import JobDatabase, get_default_db_path
from cuttle.worker.pipe_server import PipeServer
from cuttle.worker.queue import EventType, JobQueue, QueueEvent

logger = logging.getLogger(__name__)


class CuttleWorkerDaemon:
    """Manages the lifecycle of the background worker daemon."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        pipe_name: str | None = None,
        max_workers: int | None = None,
        headless: bool = False,
    ) -> None:
        self.headless = headless
        self.db = JobDatabase(db_path or get_default_db_path())
        # 1. Startup crash recovery
        recovered = self.db.recover_crashed_jobs()
        if recovered > 0:
            logger.info("Recovered %d crashed jobs from previous session.", recovered)

        # 2. UI bridge and state
        self._ui_bridge: Any = None
        self._tray: Any = None
        self._progress_windows: dict[str, Any] = {}

        # 3. Initialize job queue and pipe server
        self.queue = JobQueue(self.db, max_workers=max_workers, event_cb=self._handle_event)
        self.server = PipeServer(self.queue, pipe_name=pipe_name)
        self._running = False

    def _handle_event(self, event: QueueEvent) -> None:
        """Handle lifecycle events from the JobQueue."""
        # 1. Deliver native Windows toast notifications on completion
        if event.event_type == EventType.JOB_DONE:
            if event.status == "success" and event.output_path:
                try:
                    from cuttle.platform.windows.toast import notify_success

                    notify_success(event.output_path, original_filename=event.src_path)
                except Exception as exc:
                    logger.warning("Toast notification dispatch error: %s", exc)
            elif event.status == "failed":
                try:
                    from cuttle.platform.windows.toast import notify_error

                    notify_error(
                        event.error_msg or "Conversion failed",
                        filename=Path(event.src_path).name if event.src_path else None,
                        detail=event.error_code,
                    )
                except Exception as exc:
                    logger.warning("Toast error dispatch error: %s", exc)

        # 2. Deliver event to Qt GUI main thread if active
        if self._ui_bridge is not None:
            self._ui_bridge.event_received.emit(event)

    def start(self) -> None:
        """Start worker and block until shutdown signal."""
        self._running = True
        self.server.start()
        logger.info("Pipe server listening on %s", self.server.pipe_name)

        def _handle_signal(sig: int, frame: Any) -> None:
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        # Start desktop GUI if not headless
        if not self.headless and sys.platform == "win32":
            try:
                from PySide6.QtCore import QObject, Signal

                from cuttle.ui.progress_window import FloatingProgressWindow, get_or_create_app
                from cuttle.worker.tray import CuttleTrayIcon

                class UIEventBridge(QObject):
                    event_received = Signal(object)

                bridge = UIEventBridge()
                app = get_or_create_app()
                app.setQuitOnLastWindowClosed(False)

                tray = CuttleTrayIcon()
                tray.show()
                tray.quit_requested.connect(self.stop)
                self._tray = tray

                def _on_ui_event(event: Any) -> None:
                    # Update tray status
                    running_count = len(self.db.list_jobs(state="running"))
                    queued_count = len(self.db.list_jobs(state="queued"))
                    if self._tray:
                        self._tray.update_status(running_count, queued_count)

                    batch_id = getattr(event, "batch_id", "")
                    if not batch_id:
                        return

                    def _cancel_job(jid: str) -> None:
                        self.queue.cancel_job(jid)

                    def _cancel_batch(bid: str) -> None:
                        self.queue.cancel_batch(bid)

                    if batch_id not in self._progress_windows:
                        win = FloatingProgressWindow(
                            batch_id=batch_id,
                            on_cancel_job=_cancel_job,
                            on_cancel_batch=_cancel_batch,
                        )
                        self._progress_windows[batch_id] = win
                        win.show()

                    win = self._progress_windows[batch_id]
                    win.handle_event(event)

                bridge.event_received.connect(_on_ui_event)
                self._ui_bridge = bridge

                # Run Qt main loop
                app.exec()
                return
            except Exception as exc:
                logger.warning("Could not initialize Qt GUI, falling back to console loop: %s", exc)

        # Console loop
        try:
            while self._running:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop pipe server and job queue cleanly."""
        if not self._running:
            return
        self._running = False
        logger.info("Stopping pipe server and job queue...")
        self.server.stop()
        self.queue.shutdown(wait=True, cancel_pending=True)
        self.db.close()
        if self._tray:
            self._tray.hide()

        try:
            from PySide6.QtWidgets import QApplication

            qapp = QApplication.instance()
            if qapp:
                qapp.quit()
        except Exception:
            pass
        logger.info("Daemon exited cleanly.")


def main(argv: list[str] | None = None) -> int:
    import os

    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    log_dir = base / "Cuttle"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "worker.log"

    logging.basicConfig(
        filename=str(log_file),
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting Cuttle worker daemon process (PID %d)...", os.getpid())

    parser = argparse.ArgumentParser(description="Cuttle background worker daemon")
    parser.add_argument("--pipe", default=None, help="Custom named pipe name")
    parser.add_argument("--db", default=None, type=Path, help="Custom SQLite DB path")
    parser.add_argument("--workers", default=None, type=int, help="Max parallel conversion workers")
    parser.add_argument("--headless", action="store_true", help="Run without GUI / Tray")
    args = parser.parse_args(argv)

    daemon = CuttleWorkerDaemon(
        db_path=args.db,
        pipe_name=args.pipe,
        max_workers=args.workers,
        headless=args.headless,
    )
    try:
        daemon.start()
    except Exception as exc:
        logger.exception("Daemon crash in start(): %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
