"""Cuttle background worker daemon entry point.

Per TRD §6.6 and task card P2-05:
- Runs startup crash recovery on SQLite state database (marks orphaned jobs failed).
- Starts JobQueue concurrency controller.
- Starts Windows Named Pipe server for right-click IPC.
- Keeps running until interrupted or shutdown command is received.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any

from cuttle.worker.db import JobDatabase, get_default_db_path
from cuttle.worker.pipe_server import PipeServer
from cuttle.worker.queue import JobQueue


class CuttleWorkerDaemon:
    """Manages the lifecycle of the background worker daemon."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        pipe_name: str | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.db = JobDatabase(db_path or get_default_db_path())
        # 1. Startup crash recovery
        recovered = self.db.recover_crashed_jobs()
        if recovered > 0:
            print(f"[Worker] Recovered {recovered} crashed jobs from previous session.")

        # 2. Initialize job queue and pipe server
        self.queue = JobQueue(self.db, max_workers=max_workers)
        self.server = PipeServer(self.queue, pipe_name=pipe_name)
        self._running = False

    def start(self) -> None:
        """Start worker and block until shutdown signal."""
        self._running = True
        self.server.start()
        print(f"[Worker] Pipe server listening on {self.server.pipe_name}")

        def _handle_signal(sig: int, frame: Any) -> None:
            self.stop()

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

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
        print("[Worker] Stopping pipe server and job queue...")
        self.server.stop()
        self.queue.shutdown(wait=True, cancel_pending=True)
        self.db.close()
        print("[Worker] Daemon exited cleanly.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cuttle background worker daemon")
    parser.add_argument("--pipe", default=None, help="Custom named pipe name")
    parser.add_argument("--db", default=None, type=Path, help="Custom SQLite DB path")
    parser.add_argument("--workers", default=None, type=int, help="Max parallel conversion workers")
    args = parser.parse_args(argv)

    daemon = CuttleWorkerDaemon(
        db_path=args.db,
        pipe_name=args.pipe,
        max_workers=args.workers,
    )
    daemon.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
