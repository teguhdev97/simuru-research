from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class WebsiteRegistrationRepository:
    """Persistent metadata for explicitly authorized website QA runs.

    Passwords, OTP values, browser cookies, and mailbox credentials are never stored.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS website_registration_runs (
                    run_id TEXT PRIMARY KEY,
                    target_url TEXT NOT NULL,
                    website_host TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS website_registration_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    verification_method TEXT NOT NULL DEFAULT 'manual',
                    detail TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES website_registration_runs(run_id)
                        ON DELETE CASCADE,
                    UNIQUE(run_id, email)
                );
                CREATE INDEX IF NOT EXISTS idx_website_registration_created
                ON website_registration_runs(created_at DESC);
                """
            )
            connection.commit()

    def create_run(
        self,
        *,
        target_url: str,
        website_host: str,
        emails: list[str],
    ) -> str:
        run_id = uuid4().hex
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO website_registration_runs
                   (run_id,target_url,website_host,status,message,created_at,updated_at)
                   VALUES (?,?,?,'prepared','Inspection created; no form submitted.',?,?)""",
                (run_id, target_url, website_host, now, now),
            )
            connection.executemany(
                """INSERT INTO website_registration_identities
                   (run_id,email,status,verification_method,created_at)
                   VALUES (?,?,'prepared','manual',?)""",
                [(run_id, email, now) for email in emails],
            )
            connection.commit()
        return run_id

    def list_runs(self, *, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT run_id,target_url,website_host,status,message,error_json,created_at
                   FROM website_registration_runs
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_runs(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM website_registration_runs").fetchone()[0]
            )

    def get_run_detail(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT run_id,target_url,website_host,status,message,error_json,created_at
                   FROM website_registration_runs WHERE run_id=?""",
                (run_id,),
            ).fetchone()
            if row is None:
                return None
            identities = connection.execute(
                """SELECT email,status,verification_method,detail,created_at
                   FROM website_registration_identities WHERE run_id=? ORDER BY id""",
                (run_id,),
            ).fetchall()
        result = dict(row)
        result["identities"] = [dict(item) for item in identities]
        if result.get("error_json"):
            try:
                result["error"] = json.loads(str(result["error_json"]))
            except json.JSONDecodeError:
                result["error"] = {"raw": result["error_json"]}
        return result

    def update_run(
        self,
        run_id: str,
        *,
        status: str,
        message: str,
        error: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        error_json = json.dumps(error, ensure_ascii=False) if error is not None else None
        with self._connect() as connection:
            connection.execute(
                """UPDATE website_registration_runs
                   SET status=?,message=?,error_json=?,updated_at=? WHERE run_id=?""",
                (status, message, error_json, now, run_id),
            )
            connection.commit()

    def update_identity(
        self,
        run_id: str,
        email: str,
        *,
        status: str,
        verification_method: str = "manual",
        detail: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE website_registration_identities
                   SET status=?,verification_method=?,detail=?
                   WHERE run_id=? AND email=?""",
                (status, verification_method, detail, run_id, email),
            )
            connection.commit()
