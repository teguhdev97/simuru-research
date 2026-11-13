from __future__ import annotations

import pytest

from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.security.auth_qa import LocalAuthQAService, QAAuthError
from simuru_research.storage.database import SQLiteRepository

PASSWORD = "Local-QA-Password-123!"


def test_registration_requires_both_verification_channels(tmp_path) -> None:
    service = LocalAuthQAService(tmp_path / "qa.sqlite3")
    email = "qa-user@example.test"
    phone = "+12025550101"

    service.register_user(
        username="qa-user",
        email=email,
        phone=phone,
        password=PASSWORD,
    )

    with pytest.raises(QAAuthError, match="verification"):
        service.login(email=email, password=PASSWORD)

    email_code = service.get_test_code(channel="email", destination=email)
    sms_code = service.get_test_code(channel="sms", destination=phone)

    assert service.verify_code(channel="email", destination=email, code=email_code)
    assert service.verify_code(channel="sms", destination=phone, code=sms_code)

    token = service.login(email=email, password=PASSWORD)
    user = service.authenticate(token)

    assert user["username"] == "qa-user"
    assert user["email_verified"] == 1
    assert user["phone_verified"] == 1


def test_verification_codes_are_single_use(tmp_path) -> None:
    service = LocalAuthQAService(tmp_path / "qa.sqlite3")
    email = "single-use@example.test"

    service.register_user(
        username="single-use",
        email=email,
        phone="+12025550102",
        password=PASSWORD,
    )
    code = service.get_test_code(channel="email", destination=email)

    assert service.verify_code(channel="email", destination=email, code=code)
    with pytest.raises(QAAuthError, match="invalid or already used"):
        service.verify_code(channel="email", destination=email, code=code)


def test_login_rejects_wrong_password_and_unverified_user(tmp_path) -> None:
    service = LocalAuthQAService(tmp_path / "qa.sqlite3")
    email = "login-check@example.test"

    service.register_user(
        username="login-check",
        email=email,
        phone="+12025550103",
        password=PASSWORD,
    )

    with pytest.raises(QAAuthError, match="incorrect"):
        service.login(email=email, password="Wrong-Password-123!")

    email_code = service.get_test_code(channel="email", destination=email)
    sms_code = service.get_test_code(channel="sms", destination="+12025550103")
    service.verify_code(channel="email", destination=email, code=email_code)
    service.verify_code(channel="sms", destination="+12025550103", code=sms_code)

    with pytest.raises(QAAuthError, match="incorrect"):
        service.login(email=email, password="Wrong-Password-123!")


def test_batch_runs_forty_local_registration_verification_and_login_flows(
    tmp_path,
) -> None:
    database_path = tmp_path / "qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(database_path)

    summary = LocalRegistrationQARunner(
        repository,
        auth_service,
    ).run_batch(total_jobs=40, max_workers=3)

    assert summary.total_jobs == 40
    assert summary.max_workers == 3
    assert summary.passed == 40
    assert summary.failed == 0
    assert auth_service.count_users() == 40

    results = repository.list_results(summary.run_id)
    assert len(results) == 40
    assert all(result["status"] == "passed" for result in results)
    assert len({result["email"] for result in results}) == 40

    users = auth_service.list_users(limit=40)
    assert len(users) == 40
    assert all(user["email_verified"] == 1 for user in users)
    assert all(user["phone_verified"] == 1 for user in users)
