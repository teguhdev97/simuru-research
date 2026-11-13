from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


@dataclass(frozen=True, slots=True)
class Settings:
    simuru_base_url: str
    simuru_api_key: str | None
    database_path: Path
    default_total_jobs: int
    default_max_workers: int
    mailpit_smtp_host: str
    mailpit_smtp_port: int
    mailpit_api_url: str
    mailpit_from_email: str
    mailpit_timeout_seconds: float
    mailpit_poll_timeout_seconds: float
    mailpit_poll_interval_seconds: float

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        base_url = os.getenv("SIMURU_BASE_URL", "https://simuru.com/api").strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != "simuru.com":
            raise ValueError("SIMURU_BASE_URL must use https://simuru.com.")

        smtp_host = os.getenv("MAILPIT_SMTP_HOST", "127.0.0.1").strip()
        if smtp_host not in LOOPBACK_HOSTS:
            raise ValueError("MAILPIT_SMTP_HOST must be a loopback host.")

        api_url = os.getenv("MAILPIT_API_URL", "http://127.0.0.1:8025").strip().rstrip("/")
        mailpit_parsed = urlparse(api_url)
        if mailpit_parsed.scheme != "http" or mailpit_parsed.hostname not in LOOPBACK_HOSTS:
            raise ValueError("MAILPIT_API_URL must use HTTP on a loopback host.")

        return cls(
            simuru_base_url=base_url,
            simuru_api_key=os.getenv("SIMURU_API_KEY", "").strip() or None,
            database_path=Path(os.getenv("DATABASE_PATH", "data/simuru_research.sqlite3")),
            default_total_jobs=_read_int("DEFAULT_TOTAL_JOBS", 40, minimum=1, maximum=100),
            default_max_workers=_read_int("DEFAULT_MAX_WORKERS", 3, minimum=1, maximum=10),
            mailpit_smtp_host=smtp_host,
            mailpit_smtp_port=_read_int("MAILPIT_SMTP_PORT", 1025, minimum=1, maximum=65535),
            mailpit_api_url=api_url,
            mailpit_from_email=os.getenv(
                "MAILPIT_FROM_EMAIL",
                "no-reply@simuru.local",
            ).strip(),
            mailpit_timeout_seconds=_read_float("MAILPIT_TIMEOUT_SECONDS", 5.0),
            mailpit_poll_timeout_seconds=_read_float(
                "MAILPIT_POLL_TIMEOUT_SECONDS",
                15.0,
            ),
            mailpit_poll_interval_seconds=_read_float(
                "MAILPIT_POLL_INTERVAL_SECONDS",
                0.25,
            ),
        )


def _read_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc

    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value
