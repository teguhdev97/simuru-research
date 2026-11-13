from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._+-]+@example\.test$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{3,30}$")
PHONE_PATTERN = re.compile(r"^\+120255501\d{2}$")
PASSWORD_ITERATIONS = 310_000
OTP_TTL_MINUTES = 10
SESSION_TTL_HOURS = 1


class QAAuthError(ValueError):
    """Raised when a local QA authentication operation is invalid."""


class LocalAuthQAService:
    """Local-only registration and authentication service for internal QA.

    Email and SMS codes are delivered to a local test outbox. No email/SMS provider,
    third-party account, Instagram endpoint, or external registration page is called.
    The fictional example.test and 555-0100..0199 ranges are enforced deliberately.
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
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
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
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS qa_users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    phone TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    phone_verified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qa_test_outbox (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL CHECK (channel IN ('email', 'sms')),
                    destination TEXT NOT NULL,
                    code TEXT,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES qa_users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_qa_outbox_lookup
                ON qa_test_outbox(channel, destination, created_at DESC);

                CREATE TABLE IF NOT EXISTS qa_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES qa_users(user_id) ON DELETE CASCADE
                );
                """
            )

    def register_user(
        self,
        *,
        username: str,
        email: str,
        phone: str,
        password: str,
    ) -> str:
        clean_username = username.strip()
        clean_email = email.strip().lower()
        clean_phone = phone.strip()

        if not USERNAME_PATTERN.fullmatch(clean_username):
            raise QAAuthError("Username must contain 3-30 letters, numbers, dots, or underscores.")
        if not EMAIL_PATTERN.fullmatch(clean_email):
            raise QAAuthError("Local QA email must use the reserved example.test domain.")
        if not PHONE_PATTERN.fullmatch(clean_phone):
            raise QAAuthError("Local QA phone must use the fictional +1-202-555-0100..0199 range.")
        if len(password) < 12:
            raise QAAuthError("Password must contain at least 12 characters.")

        user_id = uuid4().hex
        now = _utc_now()
        expires_at = (datetime.now(UTC) + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
        email_code = _new_otp()
        sms_code = _new_otp()

        with self._connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO qa_users (
                        user_id, username, email, phone, password_hash,
                        email_verified, phone_verified, created_at
                    ) VALUES (?, ?, ?, ?, ?, 0, 0, ?)
                    """,
                    (
                        user_id,
                        clean_username,
                        clean_email,
                        clean_phone,
                        _hash_password(password),
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise QAAuthError("Username, email, or phone is already registered.") from exc

            connection.executemany(
                """
                INSERT INTO qa_test_outbox (
                    user_id, channel, destination, code, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (user_id, "email", clean_email, email_code, expires_at, now),
                    (user_id, "sms", clean_phone, sms_code, expires_at, now),
                ],
            )

        return user_id

    def get_test_code(self, *, channel: str, destination: str) -> str:
        """Read a code from the local-only test outbox for automated QA."""
        if channel not in {"email", "sms"}:
            raise QAAuthError("channel must be email or sms.")

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT code, expires_at
                FROM qa_test_outbox
                WHERE channel = ? AND destination = ?
                  AND consumed_at IS NULL AND code IS NOT NULL
                ORDER BY message_id DESC
                LIMIT 1
                """,
                (channel, destination.strip().lower() if channel == "email" else destination.strip()),
            ).fetchone()

        if row is None:
            raise QAAuthError("No unused verification code exists in the local test outbox.")
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.now(UTC):
            raise QAAuthError("Verification code has expired.")
        return str(row["code"])

    def verify_code(self, *, channel: str, destination: str, code: str) -> bool:
        if channel not in {"email", "sms"}:
            raise QAAuthError("channel must be email or sms.")
        if not re.fullmatch(r"\d{6}", code.strip()):
            raise QAAuthError("Verification code must contain six digits.")

        clean_destination = (
            destination.strip().lower() if channel == "email" else destination.strip()
        )
        now = datetime.now(UTC)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT message_id, user_id, expires_at
                FROM qa_test_outbox
                WHERE channel = ? AND destination = ? AND code = ?
                  AND consumed_at IS NULL
                ORDER BY message_id DESC
                LIMIT 1
                """,
                (channel, clean_destination, code.strip()),
            ).fetchone()

            if row is None:
                raise QAAuthError("Verification code is invalid or already used.")
            if datetime.fromisoformat(str(row["expires_at"])) <= now:
                raise QAAuthError("Verification code has expired.")

            verified_column = "email_verified" if channel == "email" else "phone_verified"
            connection.execute(
                f"UPDATE qa_users SET {verified_column} = 1 WHERE user_id = ?",
                (row["user_id"],),
            )
            connection.execute(
                """
                UPDATE qa_test_outbox
                SET code = NULL, consumed_at = ?
                WHERE message_id = ?
                """,
                (now.isoformat(), row["message_id"]),
            )

        return True

    def login(self, *, email: str, password: str) -> str:
        clean_email = email.strip().lower()
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT user_id, password_hash, email_verified, phone_verified
                FROM qa_users
                WHERE email = ?
                """,
                (clean_email,),
            ).fetchone()

            if row is None or not _verify_password(password, str(row["password_hash"])):
                raise QAAuthError("Email or password is incorrect.")
            if not row["email_verified"] or not row["phone_verified"]:
                raise QAAuthError("Email and phone verification must both be completed.")

            token = secrets.token_urlsafe(32)
            now = datetime.now(UTC)
            expires_at = (now + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO qa_sessions (token_hash, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_hash, row["user_id"], now.isoformat(), expires_at),
            )

        return token

    def authenticate(self, token: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT users.user_id, users.username, users.email, users.phone,
                       users.email_verified, users.phone_verified, sessions.expires_at
                FROM qa_sessions AS sessions
                JOIN qa_users AS users ON users.user_id = sessions.user_id
                WHERE sessions.token_hash = ?
                  AND sessions.revoked_at IS NULL
                  AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()

        if row is None:
            raise QAAuthError("Session is invalid or expired.")
        return dict(row)

    def list_users(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT username, email, phone, email_verified, phone_verified, created_at
                FROM qa_users
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_users(self) -> int:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM qa_users").fetchone()
        return int(row["total"])


def _new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        "pbkdf2_sha256$"
        + str(PASSWORD_ITERATIONS)
        + "$"
        + salt.hex()
        + "$"
        + digest.hex()
    )


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_text),
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
