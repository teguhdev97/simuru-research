from __future__ import annotations

import csv
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

ACCOUNT_TYPES = {"personal", "creator", "business"}
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")
CSV_COLUMNS = (
    "username",
    "owner_label",
    "account_type",
    "owner_approved",
    "notes",
)


class TeamAccountRegistry:
    """Local registry for existing team-owned Instagram accounts.

    This registry stores metadata only. It never stores passwords, OTPs, phone
    numbers, email inbox credentials, or Instagram session cookies.
    """

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS team_accounts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    owner_label TEXT NOT NULL,
                    account_type TEXT NOT NULL
                        CHECK (account_type IN ('personal', 'creator', 'business')),
                    owner_approved INTEGER NOT NULL CHECK (owner_approved = 1),
                    api_status TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_team_accounts_type
                ON team_accounts(account_type)
                """
            )

    def add_account(
        self,
        *,
        username: str,
        owner_label: str,
        account_type: str,
        owner_approved: bool,
        notes: str = "",
    ) -> bool:
        clean_username = username.strip().removeprefix("@")
        clean_owner = owner_label.strip()
        clean_type = account_type.strip().lower()

        if not USERNAME_PATTERN.fullmatch(clean_username):
            raise ValueError("Username must be 1-30 letters, numbers, dots, or underscores.")
        if not clean_owner:
            raise ValueError("Owner/team label is required.")
        if clean_type not in ACCOUNT_TYPES:
            raise ValueError("account_type must be personal, creator, or business.")
        if owner_approved is not True:
            raise ValueError("Owner authorization must be confirmed before storing an account.")

        now = datetime.now(UTC).isoformat()
        api_status = (
            "manual_only"
            if clean_type == "personal"
            else "pending_meta_oauth"
        )

        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO team_accounts (
                    username, owner_label, account_type, owner_approved,
                    api_status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    clean_username,
                    clean_owner,
                    clean_type,
                    api_status,
                    notes.strip(),
                    now,
                    now,
                ),
            )
        return cursor.rowcount == 1

    def import_csv(self, content: str, *, confirmed: bool) -> dict[str, int]:
        if not confirmed:
            raise ValueError("Confirm that every imported account is owned or authorized by the team.")

        reader = csv.DictReader(StringIO(content.lstrip("\ufeff")))
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty.")
        missing = set(CSV_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        imported = 0
        duplicates = 0
        unauthorized = 0
        invalid = 0

        for row in reader:
            approved_value = str(row.get("owner_approved", "")).strip().lower()
            if approved_value not in {"1", "true", "yes", "y"}:
                unauthorized += 1
                continue

            try:
                inserted = self.add_account(
                    username=str(row.get("username", "")),
                    owner_label=str(row.get("owner_label", "")),
                    account_type=str(row.get("account_type", "")),
                    owner_approved=True,
                    notes=str(row.get("notes", "")),
                )
            except ValueError:
                invalid += 1
                continue

            if inserted:
                imported += 1
            else:
                duplicates += 1

        return {
            "imported": imported,
            "duplicates": duplicates,
            "unauthorized": unauthorized,
            "invalid": invalid,
        }

    def list_accounts(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT username, owner_label, account_type, owner_approved,
                       api_status, notes, created_at, updated_at
                FROM team_accounts
                ORDER BY username COLLATE NOCASE
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_csv(self) -> str:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for account in self.list_accounts():
            writer.writerow(
                {
                    "username": account["username"],
                    "owner_label": account["owner_label"],
                    "account_type": account["account_type"],
                    "owner_approved": "true",
                    "notes": account["notes"],
                }
            )
        return output.getvalue()

    def count_by_type(self) -> dict[str, int]:
        counts = {account_type: 0 for account_type in sorted(ACCOUNT_TYPES)}
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT account_type, COUNT(*) AS total
                FROM team_accounts
                GROUP BY account_type
                """
            ).fetchall()
        for row in rows:
            counts[str(row["account_type"])] = int(row["total"])
        return counts
