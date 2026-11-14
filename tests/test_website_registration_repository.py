from __future__ import annotations

import json

from simuru_research.storage.website_registration import (
    WebsiteRegistrationRepository,
)


def test_create_run_stores_metadata_and_email_identities(tmp_path):
    repository = WebsiteRegistrationRepository(tmp_path / "qa.sqlite3")

    run_id = repository.create_run(
        target_url="https://staging.example.test/register",
        website_host="staging.example.test",
        emails=["qa01@example.test", "qa02@example.test"],
    )

    detail = repository.get_run_detail(run_id)

    assert detail is not None
    assert detail["status"] == "prepared"
    assert detail["website_host"] == "staging.example.test"
    assert [row["email"] for row in detail["identities"]] == [
        "qa01@example.test",
        "qa02@example.test",
    ]


def test_runs_are_paginated_and_counted(tmp_path):
    repository = WebsiteRegistrationRepository(tmp_path / "qa.sqlite3")
    for index in range(5):
        repository.create_run(
            target_url=f"https://staging-{index}.example.test/register",
            website_host=f"staging-{index}.example.test",
            emails=[f"qa{index}@example.test"],
        )

    assert repository.count_runs() == 5
    assert len(repository.list_runs(limit=2, offset=0)) == 2
    assert len(repository.list_runs(limit=2, offset=2)) == 2
    assert len(repository.list_runs(limit=2, offset=4)) == 1


def test_run_error_is_available_as_structured_json(tmp_path):
    repository = WebsiteRegistrationRepository(tmp_path / "qa.sqlite3")
    run_id = repository.create_run(
        target_url="https://staging.example.test/register",
        website_host="staging.example.test",
        emails=["qa@example.test"],
    )
    repository.update_run(
        run_id,
        status="failed",
        message="Inspection failed",
        error={"type": "TimeoutError", "message": "Page timed out"},
    )

    detail = repository.get_run_detail(run_id)

    assert detail is not None
    assert detail["error"] == {
        "type": "TimeoutError",
        "message": "Page timed out",
    }


def test_no_password_or_otp_fields_are_stored(tmp_path):
    repository = WebsiteRegistrationRepository(tmp_path / "qa.sqlite3")
    run_id = repository.create_run(
        target_url="https://staging.example.test/register",
        website_host="staging.example.test",
        emails=["qa@example.test"],
    )
    detail = repository.get_run_detail(run_id)
    serialized = json.dumps(detail).lower()

    assert detail is not None
    assert "password" not in serialized
    assert "otp" not in serialized
