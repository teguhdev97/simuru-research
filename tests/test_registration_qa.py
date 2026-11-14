from __future__ import annotations

import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from simuru_research.engine.registration_qa import LocalRegistrationQARunner
from simuru_research.security.auth_qa import LocalAuthQAService, QAAuthError
from simuru_research.storage.database import SQLiteRepository

PASSWORD = "Local-QA-Password-123!"


def _render_registration_qa(repository, auth_service, cpanel_manager) -> None:
    from simuru_research.ui.registration_qa_tab import render_registration_qa_tab

    render_registration_qa_tab(repository, auth_service, cpanel_manager)


def test_registration_requires_both_verification_channels(tmp_path) -> None:
    service = LocalAuthQAService(tmp_path / "qa.sqlite3")
    email = "qa-user@example.test"
    phone = "+12025550101"

    service.register_user(
        username="qa_user",
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

    assert user["username"] == "qa_user"
    assert user["email_verified"] == 1
    assert user["phone_verified"] == 1


def test_verification_codes_are_single_use(tmp_path) -> None:
    service = LocalAuthQAService(tmp_path / "qa.sqlite3")
    email = "single-use@example.test"

    service.register_user(
        username="single_use",
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
        username="login_check",
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


def test_batch_runs_five_local_registration_verification_and_login_flows(
    tmp_path,
) -> None:
    database_path = tmp_path / "qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(database_path)

    summary = LocalRegistrationQARunner(
        repository,
        auth_service,
    ).run_batch(total_jobs=5, max_workers=2)

    assert summary.total_jobs == 5
    assert summary.max_workers == 2
    assert summary.passed == 5
    assert summary.failed == 0
    assert auth_service.count_users() == 5

    results = repository.list_results(summary.run_id)
    assert len(results) == 5
    assert all(result["status"] == "passed" for result in results)
    assert len({result["email"] for result in results}) == 5

    users = auth_service.list_users(limit=5)
    assert len(users) == 5
    assert all(user["email_verified"] == 1 for user in users)
    assert all(user["phone_verified"] == 1 for user in users)


def test_batch_uses_supplied_domain_emails_for_local_qa(tmp_path) -> None:
    database_path = tmp_path / "qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(
        database_path,
        email_domain="teguhharits.com",
    )
    email_addresses = [
        f"qa-{index:02d}@teguhharits.com"
        for index in range(1, 6)
    ]

    summary = LocalRegistrationQARunner(
        repository,
        auth_service,
    ).run_batch(
        total_jobs=5,
        max_workers=2,
        email_addresses=email_addresses,
    )

    assert summary.passed == 5
    assert [result.email for result in summary.results] == email_addresses
    assert all(result.status == "passed" for result in summary.results)


def test_batch_rejects_duplicate_or_wrong_domain_addresses_before_creating_run(
    tmp_path,
) -> None:
    database_path = tmp_path / "qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(
        database_path,
        email_domain="teguhharits.com",
    )
    runner = LocalRegistrationQARunner(repository, auth_service)

    with pytest.raises(ValueError, match="unique"):
        runner.run_batch(
            total_jobs=2,
            max_workers=2,
            email_addresses=["one@teguhharits.com", "one@teguhharits.com"],
        )
    with pytest.raises(QAAuthError, match="teguhharits.com"):
        runner.run_batch(
            total_jobs=1,
            max_workers=1,
            email_addresses=["one@example.test"],
        )

    assert repository.list_runs(limit=None) == []


def test_registration_page_creates_five_domain_mailboxes_then_runs_two_workers(
    tmp_path,
) -> None:
    database_path = tmp_path / "qa.sqlite3"
    repository = SQLiteRepository(database_path)
    auth_service = LocalAuthQAService(
        database_path,
        email_domain="teguhharits.com",
    )
    addresses = [
        f"qa-{index:02d}@teguhharits.com"
        for index in range(1, 6)
    ]

    class FakeCpanelManager:
        mailbox_password = "configured-test-master-password"

        def create_five(self, *, save_credentials):
            assert save_credentials is False
            return [
                {
                    "email": address,
                    "password": "do-not-persist-this",
                    "status": "created",
                    "error": "",
                }
                for address in addresses
            ]

        def session_status(self):
            return {"connected": True}

    app = AppTest.from_function(
        _render_registration_qa,
        args=(repository, auth_service, FakeCpanelManager()),
    )
    app.session_state["registration_cpanel_ready"] = True
    app.run()
    app.button(key="run_registration_qa_batch").click().run()

    assert not app.exception
    assert auth_service.count_users() == 5
    assert app.session_state["latest_registration_mailboxes"] == [
        {"email": address, "status": "created", "error": ""}
        for address in addresses
    ]
    assert app.session_state["latest_registration_qa_run"]
    assert "password" not in str(app.session_state["latest_registration_mailboxes"])

    refreshed_app = AppTest.from_function(
        _render_registration_qa,
        args=(repository, auth_service, FakeCpanelManager()),
    ).run()
    assert not refreshed_app.exception
    assert any(len(frame.value) == 5 for frame in refreshed_app.dataframe)


def test_delete_all_users_cascades_to_outbox_and_sessions(tmp_path) -> None:
    database_path = tmp_path / "qa.sqlite3"
    service = LocalAuthQAService(database_path)
    email = "delete-me@example.test"
    phone = "+12025550104"

    service.register_user(
        username="delete_me",
        email=email,
        phone=phone,
        password=PASSWORD,
    )
    email_code = service.get_test_code(channel="email", destination=email)
    sms_code = service.get_test_code(channel="sms", destination=phone)
    service.verify_code(channel="email", destination=email, code=email_code)
    service.verify_code(channel="sms", destination=phone, code=sms_code)
    service.login(email=email, password=PASSWORD)

    assert service.delete_all_users() == 1
    assert service.count_users() == 0

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM qa_test_outbox").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM qa_sessions").fetchone()[0] == 0
