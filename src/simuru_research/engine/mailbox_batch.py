from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from simuru_research.models import BatchSummary, JobResult
from simuru_research.providers.mailbox import MailboxProvisioner, MailboxSettings
from simuru_research.storage.database import SQLiteRepository


class FiveMailboxBatchRunner:
    """Provision exactly five new QA mailboxes on the configured owned domain."""

    def __init__(self, repository: SQLiteRepository, settings: MailboxSettings) -> None:
        self.repository = repository
        self.settings = settings

    def run_batch(self) -> BatchSummary:
        run_id = uuid4().hex
        addresses = MailboxProvisioner(self.settings).create_five(run_id)
        self.repository.create_run(run_id=run_id, total_jobs=5, max_workers=1)
        now = datetime.now(UTC).isoformat()
        results: list[JobResult] = []
        for index, email in enumerate(addresses, start=1):
            result = JobResult(
                run_id=run_id,
                job_index=index,
                username=email.split("@", 1)[0],
                email=email,
                phone="",
                status="created",
                duration_ms=0.0,
                error=None,
                created_at=now,
            )
            self.repository.save_result(result)
            results.append(result)
        self.repository.finish_run(run_id=run_id, passed=5, failed=0)
        return BatchSummary(
            run_id=run_id,
            total_jobs=5,
            max_workers=1,
            passed=5,
            failed=0,
            results=tuple(results),
        )
