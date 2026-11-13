from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    simuru_base_url: str
    simuru_api_key: str | None
    database_path: Path
    default_total_jobs: int
    default_max_workers: int

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()

        base_url = os.getenv("SIMURU_BASE_URL", "https://simuru.com/api").strip().rstrip("/")
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != "simuru.com":
            raise ValueError("SIMURU_BASE_URL must use https://simuru.com.")

        return cls(
            simuru_base_url=base_url,
            simuru_api_key=os.getenv("SIMURU_API_KEY", "").strip() or None,
            database_path=Path(os.getenv("DATABASE_PATH", "data/simuru_research.sqlite3")),
            default_total_jobs=_read_int("DEFAULT_TOTAL_JOBS", 40, minimum=1, maximum=200),
            default_max_workers=_read_int("DEFAULT_MAX_WORKERS", 3, minimum=1, maximum=10),
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
