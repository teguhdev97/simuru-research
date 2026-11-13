from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from uuid import uuid4

from simuru_research.models import BatchSummary, JobResult
from simuru_research.providers.sandbox import SandboxProvider
from simuru_research.storage.database import SQLiteRepository


class BatchRunner:
    """Run synthetic QA jobs locally with a bounded thread pool."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository
        self.provider = SandboxProvider()

    def run_batch(self, *, total_jobs: int = 40, max_workers: int = 3) -> BatchSummary:
        if not 1 <= total_jobs <= 100:
            raise ValueError("total_jobs must be between 1 and 100.")
        if not 1 <= max_workers <= 10:
            raise ValueError("max_workers must be between 1 and 10.")

        run_id = uuid4().hex
        self.repository.create_run(
            run_id=run_id,
            total_jobs=total_jobs,
            max_workers=max_workers,
        )

        results: list[JobResult] = []
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="sandbox-qa",
        ) as executor:
            futures = {
                executor.submit(self._run_one, run_id, job_index): job_index
                for job_index in range(1, total_jobs + 1)
            }

            for future in as_completed(futures):
                job_index = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = JobResult(
                        run_id=run_id,
                        job_index=job_index,
                        username=f"qa-{job_index:03d}",
                        email=f"worker-error-{job_index:03d}@example.test",
                        phone="",
                        status="failed",
                        duration_ms=0.0,
                        error=type(exc).__name__,
                        created_at=_utc_now(),
                    )

                self.repository.save_result(result)
                results.append(result)

        results.sort(key=lambda item: item.job_index)
        passed = sum(item.status == "passed" for item in results)
        failed = len(results) - passed
        self.repository.finish_run(run_id=run_id, passed=passed, failed=failed)

        return BatchSummary(
            run_id=run_id,
            total_jobs=total_jobs,
            max_workers=max_workers,
            passed=passed,
            failed=failed,
            results=tuple(results),
        )

    def _run_one(self, run_id: str, job_index: int) -> JobResult:
        started = time.perf_counter()
        identity = self.provider.create_identity(job_index, run_id)

        # A tiny local delay makes concurrency observable without contacting any service.
        time.sleep(0.01)

        if not identity.email.endswith("@example.test"):
            raise ValueError("Sandbox email domain validation failed.")
        if not identity.phone.startswith("+1202555"):
            raise ValueError("Sandbox phone range validation failed.")

        return JobResult(
            run_id=run_id,
            job_index=job_index,
            username=identity.username,
            email=identity.email,
            phone=identity.phone,
            status="passed",
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            error=None,
            created_at=_utc_now(),
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
