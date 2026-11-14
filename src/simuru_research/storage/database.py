from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from simuru_research.models import JobResult


class SQLiteRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    total_jobs INTEGER NOT NULL,
                    max_workers INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    passed INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS job_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    job_index INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, job_index),
                    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_job_results_run_id
                ON job_results(run_id, job_index);
                """
            )

    def create_run(self, *, run_id: str, total_jobs: int, max_workers: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO runs (run_id, total_jobs, max_workers, status, started_at)
                VALUES (?, ?, ?, 'running', ?)
                """,
                (run_id, total_jobs, max_workers, datetime.now(UTC).isoformat()),
            )

    def save_result(self, result: JobResult) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO job_results (
                    run_id, job_index, username, email, phone, status,
                    duration_ms, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.job_index,
                    result.username,
                    result.email,
                    result.phone,
                    result.status,
                    result.duration_ms,
                    result.error,
                    result.created_at,
                ),
            )

    def finish_run(self, *, run_id: str, passed: int, failed: int) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'completed', passed = ?, failed = ?, finished_at = ?
                WHERE run_id = ?
                """,
                (passed, failed, datetime.now(UTC).isoformat(), run_id),
            )

    def list_runs(self, *, limit: int | None = 50) -> list[dict[str, object]]:
        query = """
            SELECT run_id, total_jobs, max_workers, status, passed, failed,
                   started_at, finished_at
            FROM runs
            ORDER BY started_at DESC
        """
        with self._connection() as connection:
            if limit is None:
                rows = connection.execute(query).fetchall()
            else:
                rows = connection.execute(
                    f"{query} LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_results(self, run_id: str) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT job_index, username, email, phone, status,
                       duration_ms, error, created_at
                FROM job_results
                WHERE run_id = ?
                ORDER BY job_index
                """,
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]
