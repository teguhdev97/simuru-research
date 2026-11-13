from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SandboxIdentity:
    username: str
    email: str
    phone: str


@dataclass(frozen=True, slots=True)
class JobResult:
    run_id: str
    job_index: int
    username: str
    email: str
    phone: str
    status: str
    duration_ms: float
    error: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BatchSummary:
    run_id: str
    total_jobs: int
    max_workers: int
    passed: int
    failed: int
    results: tuple[JobResult, ...]
