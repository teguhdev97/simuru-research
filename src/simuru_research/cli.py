from __future__ import annotations

import argparse
import json

from simuru_research.config.settings import Settings
from simuru_research.engine.runner import BatchRunner
from simuru_research.storage.database import SQLiteRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local synthetic QA jobs for Simuru Research."
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="Number of synthetic jobs (1-200).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Concurrent local workers (1-10).",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    repository = SQLiteRepository(settings.database_path)
    summary = BatchRunner(repository).run_batch(
        total_jobs=(
            settings.default_total_jobs if args.jobs is None else args.jobs
        ),
        max_workers=(
            settings.default_max_workers if args.workers is None else args.workers
        ),
    )

    print(
        json.dumps(
            {
                "run_id": summary.run_id,
                "total_jobs": summary.total_jobs,
                "max_workers": summary.max_workers,
                "passed": summary.passed,
                "failed": summary.failed,
                "database": str(settings.database_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
