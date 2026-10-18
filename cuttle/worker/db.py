"""State database for tracking Cuttle background conversion jobs in SQLite.

Per TRD §6.7 and task card P2-02:
- Stores jobs in %LOCALAPPDATA%\\Cuttle\\state.db.
- State machine: queued -> running -> validating -> success / failed / cancelled.
- Startup crash recovery: resets orphaned 'running' or 'validating' jobs to 'failed'
  with error E_TOOL_FAILED.
- WAL mode enabled for concurrent read/write resilience.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_STATES = frozenset({"queued", "running", "validating", "success", "failed", "cancelled"})


def get_default_db_path() -> Path:
    """Return the platform-specific default path for state.db."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".cuttle"
    target_dir = base / "Cuttle"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "state.db"


@dataclass(frozen=True)
class JobRecord:
    """Immutable snapshot of a job record from the database."""

    id: str
    batch_id: str
    src_path: str
    dst_fmt: str
    state: str
    output_path: str | None
    quality: str | None
    error_code: str | None
    error_msg: str | None
    warnings: list[str]
    created_at: float
    updated_at: float


class JobDatabase:
    """Thread-safe SQLite manager for conversion job tracking and crash recovery."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._path: str
        if db_path is None:
            self._path = str(get_default_db_path())
        elif isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._path = str(db_path)
        else:
            self._path = db_path

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            self._path,
            check_same_thread=False,
            autocommit=True,
        )
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            if self._path != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    src_path TEXT NOT NULL,
                    dst_fmt TEXT NOT NULL,
                    state TEXT NOT NULL,
                    output_path TEXT,
                    quality TEXT,
                    error_code TEXT,
                    error_msg TEXT,
                    warnings TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);")
            self._conn.commit()

    @staticmethod
    def _row_to_record(row: tuple[Any, ...]) -> JobRecord:
        warnings_raw = row[9]
        warnings_list: list[str] = []
        if warnings_raw:
            try:
                parsed = json.loads(warnings_raw)
                if isinstance(parsed, list):
                    warnings_list = [str(w) for w in parsed]
            except Exception:
                pass

        return JobRecord(
            id=row[0],
            batch_id=row[1],
            src_path=row[2],
            dst_fmt=row[3],
            state=row[4],
            output_path=row[5],
            quality=row[6],
            error_code=row[7],
            error_msg=row[8],
            warnings=warnings_list,
            created_at=row[10],
            updated_at=row[11],
        )

    def recover_crashed_jobs(self) -> int:
        """Mark any job left in 'running' or 'validating' as 'failed' (E_TOOL_FAILED).

        Returns:
            The number of crashed jobs recovered.
        """
        now = time.time()
        err_msg = "Worker terminated unexpectedly while job was in progress"
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE jobs
                SET state = 'failed',
                    error_code = 'E_TOOL_FAILED',
                    error_msg = ?,
                    updated_at = ?
                WHERE state IN ('running', 'validating');
                """,
                (err_msg, now),
            )
            count = cursor.rowcount
            self._conn.commit()
            return count

    def insert_job(
        self,
        job_id: str,
        batch_id: str,
        src_path: str,
        dst_fmt: str,
        *,
        state: str = "queued",
    ) -> JobRecord:
        """Insert a new job into the database."""
        if state not in VALID_STATES:
            raise ValueError(f"Invalid job state: {state}")

        now = time.time()
        clean_fmt = dst_fmt.lower().lstrip(".")
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (
                    id, batch_id, src_path, dst_fmt, state,
                    output_path, quality, error_code, error_msg, warnings,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, '[]', ?, ?);
                """,
                (job_id, batch_id, src_path, clean_fmt, state, now, now),
            )
            self._conn.commit()

        rec = self.get_job(job_id)
        if rec is None:
            raise RuntimeError(f"Failed to retrieve newly inserted job: {job_id}")
        return rec

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch a job record by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, batch_id, src_path, dst_fmt, state,
                       output_path, quality, error_code, error_msg, warnings,
                       created_at, updated_at
                FROM jobs
                WHERE id = ?;
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def list_jobs(
        self,
        *,
        batch_id: str | None = None,
        state: str | None = None,
    ) -> list[JobRecord]:
        """List jobs matching optional batch_id and state filters."""
        query = (
            "SELECT id, batch_id, src_path, dst_fmt, state, "
            "output_path, quality, error_code, error_msg, warnings, "
            "created_at, updated_at FROM jobs"
        )
        conditions: list[str] = []
        params: list[Any] = []

        if batch_id is not None:
            conditions.append("batch_id = ?")
            params.append(batch_id)
        if state is not None:
            conditions.append("state = ?")
            params.append(state)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at ASC;"

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    def update_state(
        self,
        job_id: str,
        state: str,
        *,
        output_path: str | None = None,
        quality: str | None = None,
        error_code: str | None = None,
        error_msg: str | None = None,
        warnings: list[str] | None = None,
    ) -> JobRecord | None:
        """Update the state and optional outcome fields of an existing job."""
        if state not in VALID_STATES:
            raise ValueError(f"Invalid job state: {state}")

        now = time.time()
        existing = self.get_job(job_id)
        if existing is None:
            return None

        # Determine effective values (preserve existing if not overridden)
        eff_output = output_path if output_path is not None else existing.output_path
        eff_quality = quality if quality is not None else existing.quality
        eff_error_code = error_code if error_code is not None else existing.error_code
        eff_error_msg = error_msg if error_msg is not None else existing.error_msg
        eff_warnings = warnings if warnings is not None else existing.warnings
        warnings_json = json.dumps(eff_warnings)

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                UPDATE jobs
                SET state = ?,
                    output_path = ?,
                    quality = ?,
                    error_code = ?,
                    error_msg = ?,
                    warnings = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    state,
                    eff_output,
                    eff_quality,
                    eff_error_code,
                    eff_error_msg,
                    warnings_json,
                    now,
                    job_id,
                ),
            )
            self._conn.commit()

        return self.get_job(job_id)

    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> JobDatabase:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
