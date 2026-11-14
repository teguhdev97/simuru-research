from __future__ import annotations

import imaplib
from dataclasses import replace

import pytest

from simuru_research.providers.imap_inbox import ImapInboxReader
from simuru_research.providers.mailbox import MailboxError, MailboxSettings


def settings(**overrides: object) -> MailboxSettings:
    values: dict[str, object] = {
        "domain": "example.test",
        "prefix": "qa",
        "cpanel_host": "cpanel.example.test",
        "cpanel_username": "test-user",
        "cpanel_api_token": "test-token",
        "mailbox_master_password": "local-test-secret",
        "mailbox_quota_mb": 50,
        "imap_host": "mail.example.test",
        "imap_port": 993,
        "smtp_host": "mail.example.test",
        "smtp_port": 465,
        "sender_allowlist": (),
        "subject_keywords": (),
        "mailbox_passwords": {"qa-one@example.test": "mailbox-password"},
    }
    values.update(overrides)
    return MailboxSettings(**values)


def test_list_messages_uses_read_only_inbox_and_peek_headers(monkeypatch):
    observed: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            observed["connection"] = (args, kwargs)

        def __enter__(self):
            observed["entered"] = True
            return self

        def __exit__(self, *args):
            observed["exited"] = True

        def login(self, email, password):
            observed["login"] = (email, password)
            return "OK", []

        def select(self, mailbox, *, readonly):
            observed["select"] = (mailbox, readonly)
            return "OK", []

        def search(self, charset, criteria):
            assert charset is None
            assert criteria == "ALL"
            return "OK", [b"1 2"]

        def fetch(self, message_id, query):
            observed.setdefault("fetches", []).append((message_id, query))
            subject = b"First" if message_id == b"1" else b"Second"
            raw = b"From: sender@example.test\r\nSubject: " + subject + b"\r\n\r\n"
            return "OK", [(b"header", raw)]

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    reader = ImapInboxReader(settings())

    messages = reader.list_messages("QA-ONE@EXAMPLE.TEST")

    assert [message.message_id for message in messages] == ["2", "1"]
    assert messages[0].subject == "Second"
    assert observed["login"] == ("qa-one@example.test", "mailbox-password")
    assert observed["select"] == ("INBOX", True)
    assert observed["exited"] is True
    assert all("BODY.PEEK" in query for _, query in observed["fetches"])


def test_read_message_extracts_plain_text_without_marking_read(monkeypatch):
    observed: dict[str, object] = {}
    raw_message = (
        b"From: sender@example.test\r\n"
        b"Subject: Safe message\r\n"
        b"Date: Wed, 01 Jan 2025 12:00:00 +0000\r\n"
        b"Content-Type: text/html; charset=utf-8\r\n"
        b"\r\n"
        b"<html><body><p>Hello</p><script>doNotShow()</script>"
        b"<div>Inbox content</div></body></html>"
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def login(self, email, password):
            return "OK", []

        def select(self, mailbox, *, readonly):
            assert readonly is True
            return "OK", []

        def fetch(self, message_id, query):
            observed["fetch"] = (message_id, query)
            return "OK", [(b"message", raw_message)]

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    message = ImapInboxReader(settings()).read_message(
        "qa-one@example.test",
        "42",
    )

    assert message["subject"] == "Safe message"
    assert "Hello" in message["body"]
    assert "Inbox content" in message["body"]
    assert "doNotShow" not in message["body"]
    assert observed["fetch"] == (b"42", "(BODY.PEEK[])")


@pytest.mark.parametrize(
    "destination",
    [
        "qa-one@other.test",
        "qa-one@example.test@EXAMPLE.TEST",
        "qa-invalid name@example.test",
        "user@example.test",
    ],
)
def test_reader_rejects_invalid_or_out_of_scope_addresses(destination):
    class EmptyVault:
        def get(self, email):
            pytest.fail("Credentials must not be checked for invalid addresses.")

    reader = ImapInboxReader(settings(), credential_vault=EmptyVault())
    with pytest.raises(MailboxError):
        reader.list_messages(destination)


def test_reader_requires_configured_credential_before_connecting(monkeypatch):
    class EmptyVault:
        def get(self, email):
            return None

    monkeypatch.setattr(
        "imaplib.IMAP4_SSL",
        lambda *args, **kwargs: pytest.fail("IMAP must not connect without credentials."),
    )
    reader = ImapInboxReader(
        replace(settings(), mailbox_passwords={}, mailbox_master_password=""),
        credential_vault=EmptyVault(),
    )
    with pytest.raises(MailboxError, match="password"):
        reader.list_messages("qa-one@example.test")


def test_reader_uses_master_password_when_mailbox_password_is_not_mapped(monkeypatch):
    observed: dict[str, str] = {}

    class EmptyVault:
        def get(self, email):
            pytest.fail("The configured master password should be used first.")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def login(self, email, password):
            observed["password"] = password
            return "OK", []

        def select(self, mailbox, *, readonly):
            return "OK", []

        def search(self, charset, criteria):
            return "OK", [b""]

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    reader = ImapInboxReader(
        replace(
            settings(),
            mailbox_passwords={},
            mailbox_master_password="env-master-password",
        ),
        credential_vault=EmptyVault(),
    )

    reader.list_messages("qa-one@example.test")

    assert observed["password"] == "env-master-password"


def test_reader_uses_temporary_mailbox_password_before_master_password(monkeypatch):
    observed: dict[str, str] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def login(self, email, password):
            observed["password"] = password
            return "OK", []

        def select(self, mailbox, *, readonly):
            return "OK", []

        def search(self, charset, criteria):
            return "OK", [b""]

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    reader = ImapInboxReader(
        replace(
            settings(),
            mailbox_passwords={"qa-one@example.test": "temporary-password"},
            mailbox_master_password="env-master-password",
        )
    )

    reader.list_messages("qa-one@example.test")

    assert observed["password"] == "temporary-password"


def test_reader_can_allow_non_qa_mailboxes_for_domain_inbox():
    reader = ImapInboxReader(
        settings(),
        allow_non_qa_mailboxes=True,
    )
    assert reader._validate_destination("owner@example.test") == "owner@example.test"
    with pytest.raises(MailboxError, match="outside"):
        reader._validate_destination("owner@other.test")


def test_reader_rejects_invalid_message_ids():
    reader = ImapInboxReader(settings())
    with pytest.raises(MailboxError, match="identifier"):
        reader.read_message("qa-one@example.test", "1 BODY[]")


def test_reader_explains_rejected_mailbox_credentials(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def login(self, email, password):
            raise imaplib.IMAP4.error(
                b"[AUTHENTICATIONFAILED] Authentication failed."
            )

    monkeypatch.setattr("imaplib.IMAP4_SSL", FakeClient)
    with pytest.raises(MailboxError, match="password mailbox"):
        ImapInboxReader(settings()).list_messages("qa-one@example.test")
