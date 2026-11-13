from __future__ import annotations

from simuru_research.engine.runner import BatchRunner
from simuru_research.storage.database import SQLiteRepository


def test_runs_forty_synthetic_jobs_and_persists_them(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "test.sqlite3")

    summary = BatchRunner(repository).run_batch(total_jobs=40, max_workers=3)

    assert summary.total_jobs == 40
    assert summary.max_workers == 3
    assert summary.passed == 40
    assert summary.failed == 0

    rows = repository.list_results(summary.run_id)
    assert len(rows) == 40
    assert len({row["email"] for row in rows}) == 40
    assert all(str(row["email"]).endswith("@example.test") for row in rows)
    assert all(str(row["phone"]).startswith("+1202555") for row in rows)

    run = repository.list_runs(limit=1)[0]
    assert run["run_id"] == summary.run_id
    assert run["status"] == "completed"


def test_rejects_unsafe_worker_limits(tmp_path) -> None:
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    runner = BatchRunner(repository)

    try:
        runner.run_batch(total_jobs=40, max_workers=40)
    except ValueError as exc:
        assert "max_workers" in str(exc)
    else:
        raise AssertionError("Expected max_workers validation to fail.")
