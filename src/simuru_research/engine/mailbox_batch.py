from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from simuru_research.models import JobResult, BatchSummary
from simuru_research.providers.mailbox import MailboxProvisioner, MailboxSettings
from simuru_research.storage.database import SQLiteRepository


class FiveMailboxBatchRunner:
    """Create a deterministic five-address QA batch from pre-created domain mailboxes.

    Mailbox creation itself is provider-specific. This runner selects exactly five
    mailbox addresses and persists a batch inventory. It never signs up to a third-party
    site or submits registration forms.
    """

    def __init__(self, repository: SQLiteRepository, settings: MailboxSettings) -> None:
        self.repository = repository
        self.settings = settings

    def run_batch(self) -> BatchSummary:
        run_id = uuid4().hex
        addresses = MailboxProvisioner(self.settings).addresses_for_batch(run_id)
        self.repository.create_run(run_id=run_id, total_jobs=5, max_workers=1)
        now = datetime.now(UTC).isoformat()
        results = []
        for index, email in enumerate(addresses, start=1):
            username = email.split("@", 1)[0]
            result = JobResult(
                run_id=run_id,
                job_index=index,
                username=username,
                email=email,
                phone="",
                status="ready",
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
