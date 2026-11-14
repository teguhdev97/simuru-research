from __future__ import annotations

import secrets
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from simuru_research.models import BatchSummary, JobResult
from simuru_research.providers.sandbox import SandboxProvider
from simuru_research.security.auth_qa import LocalAuthQAService
from simuru_research.storage.database import SQLiteRepository


class LocalRegistrationQARunner:
    """Exercise a local registration, email/SMS verification, and login workflow."""

    def __init__(
        self,
        repository: SQLiteRepository,
        auth_service: LocalAuthQAService,
    ) -> None:
        self.repository = repository
        self.auth_service = auth_service
        self.identity_provider = SandboxProvider()

    def run_batch(
        self,
        *,
        total_jobs: int = 40,
        max_workers: int = 3,
        email_addresses: Sequence[str] | None = None,
    ) -> BatchSummary:
        if not 1 <= total_jobs <= 100:
            raise ValueError("total_jobs must be between 1 and 100.")
        if not 1 <= max_workers <= 10:
            raise ValueError("max_workers must be between 1 and 10.")
        normalized_emails = None
        if email_addresses is not None:
            if len(email_addresses) != total_jobs:
                raise ValueError("email_addresses must contain one address per job.")
            normalized_emails = [
                self.auth_service.normalize_email(email)
                for email in email_addresses
            ]
            if len(set(normalized_emails)) != total_jobs:
                raise ValueError("email_addresses must be unique.")

        run_id = uuid4().hex
        self.repository.create_run(
            run_id=run_id,
            total_jobs=total_jobs,
            max_workers=max_workers,
        )

        results: list[JobResult] = []
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="registration-qa",
        ) as executor:
            futures = {
                executor.submit(
                    self._run_one,
                    run_id,
                    index,
                    normalized_emails[index - 1] if normalized_emails else None,
                ): index
                for index in range(1, total_jobs + 1)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    identity = self.identity_provider.create_identity(index, run_id)
                    email = (
                        normalized_emails[index - 1]
                        if normalized_emails
                        else identity.email
                    )
                    result = JobResult(
                        run_id=run_id,
                        job_index=index,
                        username=identity.username,
                        email=email,
                        phone=identity.phone,
                        status="failed",
                        duration_ms=0.0,
                        error=type(exc).__name__,
                        created_at=_utc_now(),
                    )

                self.repository.save_result(result)
                results.append(result)

        results.sort(key=lambda result: result.job_index)
        passed = sum(result.status == "passed" for result in results)
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

    def _run_one(
        self,
        run_id: str,
        job_index: int,
        email_address: str | None = None,
    ) -> JobResult:
        started = time.perf_counter()
        identity = self.identity_provider.create_identity(job_index, run_id)
        if email_address is not None:
            identity = replace(identity, email=email_address)
        password = "QA!" + secrets.token_urlsafe(18) + "Aa9"

        self.auth_service.register_user(
            username=identity.username,
            email=identity.email,
            phone=identity.phone,
            password=password,
        )

        email_code = self.auth_service.get_test_code(
            channel="email",
            destination=identity.email,
        )
        self.auth_service.verify_code(
            channel="email",
            destination=identity.email,
            code=email_code,
        )

        sms_code = self.auth_service.get_test_code(
            channel="sms",
            destination=identity.phone,
        )
        self.auth_service.verify_code(
            channel="sms",
            destination=identity.phone,
            code=sms_code,
        )

        token = self.auth_service.login(email=identity.email, password=password)
        authenticated_user = self.auth_service.authenticate(token)
        if authenticated_user["username"] != identity.username:
            raise RuntimeError("Authenticated user does not match the registered identity.")
        if not authenticated_user["email_verified"] or not authenticated_user["phone_verified"]:
            raise RuntimeError("The local QA user is not fully verified.")

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
