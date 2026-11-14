from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from simuru_research.providers.mailbox import MailboxSettings
from simuru_research.ui import mailbox_inbox
from simuru_research.ui.mailbox_inbox import (
    _email_button_label,
    _mailbox_password_key,
    _newest_created_first,
)
from simuru_research.ui.pagination import paginate_items


def test_newest_successfully_created_mailboxes_are_listed_first():
    addresses = [
        "owner@example.test",
        "qa-older@example.test",
        "qa-new-01@example.test",
        "qa-new-02@example.test",
    ]
    latest_batch = [
        {"email": "qa-new-01@example.test", "status": "created"},
        {"email": "qa-new-02@example.test", "status": "created"},
    ]

    assert _newest_created_first(addresses, latest_batch) == [
        "qa-new-02@example.test",
        "qa-new-01@example.test",
        "owner@example.test",
        "qa-older@example.test",
    ]


def test_newest_first_keeps_failed_or_missing_batch_addresses_in_api_order():
    addresses = ["owner@example.test", "qa-new@example.test"]
    latest_batch = [
        {"email": "qa-new@example.test", "status": "failed"},
    ]

    assert _newest_created_first(addresses, latest_batch) == addresses


def test_email_button_label_truncates_long_addresses_with_ellipsis():
    address = "qa-test-with-a-long-local-part@example.test"
    assert _email_button_label(address) == "qa-test-with-a-long-local-part@ex..."


def test_email_button_label_preserves_short_addresses():
    assert _email_button_label("qa@example.test") == "qa@example.test"


def test_email_pagination_defaults_to_six_addresses_and_clamps_page():
    addresses = [f"qa-{index}@example.test" for index in range(23)]

    first_page, page, page_count = paginate_items(addresses, 1, 6)
    last_page, last_page_number, _ = paginate_items(addresses, 99, 6)

    assert first_page == addresses[:6]
    assert page == 1
    assert page_count == 4
    assert last_page == addresses[18:]
    assert last_page_number == 4


def test_email_pagination_handles_empty_lists_and_invalid_page_size():
    assert paginate_items([], 1, 6) == ([], 1, 1)
    with pytest.raises(ValueError, match="page_size"):
        paginate_items(["qa@example.test"], 1, page_size=0)


def test_configured_password_auto_loads_once_without_vault_access(monkeypatch):
    settings = MailboxSettings(
        domain="example.test",
        prefix="qa",
        cpanel_host="",
        cpanel_username="",
        cpanel_api_token="",
        mailbox_master_password="test-only-password",
        mailbox_quota_mb=50,
        imap_host="mail.example.test",
        imap_port=993,
        smtp_host="mail.example.test",
        smtp_port=465,
        sender_allowlist=(),
        subject_keywords=(),
    )
    loads: list[str] = []
    monkeypatch.setattr(
        MailboxSettings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    monkeypatch.setattr(
        mailbox_inbox.MailboxCredentialVault,
        "get",
        lambda self, email: (_ for _ in ()).throw(
            AssertionError("The configured environment password takes precedence.")
        ),
    )
    monkeypatch.setattr(
        mailbox_inbox,
        "_load_inbox",
        lambda manager, email, password_override=None: (
            loads.append(email) or {"email": email, "messages": []}
        ),
    )

    def render() -> None:
        from types import SimpleNamespace

        import streamlit as st

        from simuru_research.ui import mailbox_inbox

        manager = SimpleNamespace(domain="example.test", prefix="qa")
        st.session_state["domain_email_addresses"] = ["qa-one@example.test"]
        st.session_state["domain_email_refresh_available"] = True
        mailbox_inbox.render_mailbox_inbox(manager)

    app = AppTest.from_function(render).run()
    assert not app.exception
    assert loads == ["qa-one@example.test"]
    assert (
        app.session_state[_mailbox_password_key("qa-one@example.test")]
        == "test-only-password"
    )

    app.run()
    assert not app.exception
    assert loads == ["qa-one@example.test"]
