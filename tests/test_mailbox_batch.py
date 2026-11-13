from __future__ import annotations

import httpx
import pytest

from simuru_research.engine.mailbox_batch import FiveMailboxBatchRunner
from simuru_research.providers.mailbox import (
    MailboxError,
    MailboxProvisioner,
    MailboxSettings,
)
from simuru_research.storage.database import SQLiteRepository


def settings(**overrides):
    values = {
        "domain": "teguhharits.com",
        "prefix": "qa",
        "cpanel_host": "cpanel.teguhharits.com",
        "cpanel_username": "cpaneluser",
        "cpanel_api_token": "test-token",
        "mailbox_master_password": "A-long-local-test-secret-not-for-production-123!",
        "mailbox_quota_mb": 50,
        "imap_host": "mail.teguhharits.com",
        "imap_port": 993,
        "smtp_host": "mail.teguhharits.com",
        "smtp_port": 465,
        "sender_allowlist": ("noreply@staging.example.test",),
        "subject_keywords": ("verification", "otp"),
    }
    values.update(overrides)
    return MailboxSettings(**values)


def test_password_derivation_is_stable_and_unique_per_address():
    provisioner = MailboxProvisioner(settings())
    first = provisioner.password_for("qa-abcdef12-01@teguhharits.com")
    second = provisioner.password_for("qa-abcdef12-02@teguhharits.com")
    assert first == provisioner.password_for("qa-abcdef12-01@teguhharits.com")
    assert first != second
    assert len(first) >= 32


def test_provisioner_rejects_missing_api_credentials():
    provisioner = MailboxProvisioner(settings(cpanel_api_token=""))
    with pytest.raises(MailboxError, match="QA_CPANEL"):
        provisioner.create_five("abcdef1234567890")


def test_mailbox_batch_creates_exactly_five_and_saves_run(monkeypatch, tmp_path):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"status": 1, "data": "created"}}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, *, headers, params):
            calls.append((url, headers, params))
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: FakeClient())
    repository = SQLiteRepository(tmp_path / "qa.sqlite3")
    summary = FiveMailboxBatchRunner(repository, settings()).run_batch()

    assert summary.total_jobs == 5
    assert summary.passed == 5
    assert len(calls) == 5
    assert len({call[2]["email"] for call in calls}) == 5
    assert all(call[2]["domain"] == "teguhharits.com" for call in calls)
    assert len(repository.list_results(summary.run_id)) == 5


def test_mailbox_batch_stops_when_provider_rejects_creation(monkeypatch, tmp_path):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"status": 0, "errors": ["not allowed"]}}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, *, headers, params):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", lambda **kwargs: FakeClient())
    repository = SQLiteRepository(tmp_path / "qa.sqlite3")
    with pytest.raises(MailboxError, match="cPanel rejected"):
        FiveMailboxBatchRunner(repository, settings()).run_batch()



def test_imap_reader_uses_actual_injected_mailbox_password(monkeypatch):
    from simuru_research.providers.mailbox import ImapOTPReader

    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def login(self, email, password):
            calls.append((email, password))
            return "OK", []
        def select(self, mailbox, readonly=True):
            assert mailbox == "INBOX"
            return "OK", []
        def logout(self):
            return "BYE", []

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    config = settings()
    config = __import__("dataclasses").replace(
        config,
        mailbox_passwords={"qa-test-01@teguhharits.com": "actual-cpanel-password"},
    )
    reader = ImapOTPReader(config)
    reader.check_connection("qa-test-01@teguhharits.com")
    assert calls == [("qa-test-01@teguhharits.com", "actual-cpanel-password")]


def test_imap_reader_requires_existing_credential(monkeypatch):
    from simuru_research.providers.mailbox import ImapOTPReader

    config = __import__("dataclasses").replace(settings(), mailbox_passwords={})
    reader = ImapOTPReader(config, credential_vault=type("Vault", (), {"get": lambda self, email: None})())
    with pytest.raises(MailboxError, match="credential"):
        reader.check_connection("qa-test-01@teguhharits.com")
