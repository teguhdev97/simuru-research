from __future__ import annotations

from simuru_research.models import SandboxIdentity


class SandboxProvider:
    """Generate fictional identities for local QA; never contacts an email/SMS provider."""

    def create_identity(self, job_index: int, run_id: str) -> SandboxIdentity:
        if not 1 <= job_index <= 100:
            raise ValueError("job_index must be between 1 and 100.")

        suffix = run_id.replace("-", "")[:8]
        phone_suffix = 99 + job_index
        return SandboxIdentity(
            username=f"qa_{suffix}_{job_index:03d}",
            email=f"qa-{suffix}-{job_index:03d}@example.test",
            phone=f"+120255501{phone_suffix:04d}",
        )
