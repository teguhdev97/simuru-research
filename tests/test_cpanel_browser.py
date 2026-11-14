from __future__ import annotations

from contextlib import contextmanager

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager


def test_cpanel_browser_manager_requires_https():
    try:
        CpanelBrowserMailboxManager(cpanel_url="http://example.test:2083", domain="teguhharits.com")
    except Exception as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP cPanel URL must be rejected")


def test_cpanel_browser_manager_rejects_invalid_quota():
    try:
        CpanelBrowserMailboxManager(
            cpanel_url="https://cpanel.example.test:2083",
            domain="teguhharits.com",
            quota_mb=0,
        )
    except Exception as exc:
        assert "quota" in str(exc).lower()
    else:
        raise AssertionError("Invalid quota must be rejected")



def test_uapi_succeeded_accepts_numeric_and_string_status():
    assert CpanelBrowserMailboxManager._uapi_succeeded({"result": {"status": 1}})
    assert CpanelBrowserMailboxManager._uapi_succeeded({"result": {"status": "1"}})


def test_uapi_succeeded_rejects_failed_or_missing_status():
    assert not CpanelBrowserMailboxManager._uapi_succeeded({"result": {"status": 0}})
    assert not CpanelBrowserMailboxManager._uapi_succeeded({"result": {}})



def test_uapi_result_accepts_standard_nested_envelope():
    payload = {"result": {"status": 1, "data": [{"email": "qa@example.test"}]}}
    result = CpanelBrowserMailboxManager._uapi_result(payload)
    assert result["status"] == 1
    assert CpanelBrowserMailboxManager._uapi_succeeded(payload)


def test_uapi_result_accepts_direct_envelope():
    payload = {"status": "1", "data": [{"email": "qa@example.test"}], "errors": None}
    result = CpanelBrowserMailboxManager._uapi_result(payload)
    assert result["status"] == "1"
    assert CpanelBrowserMailboxManager._uapi_succeeded(payload)


def test_uapi_result_accepts_legacy_cpanelresult_envelope():
    payload = {
        "cpanelresult": {
            "event": {"result": 1},
            "data": [{"email": "qa@example.test"}],
        }
    }
    result = CpanelBrowserMailboxManager._uapi_result(payload)
    assert result["status"] == 1
    assert len(result["data"]) == 1
    assert CpanelBrowserMailboxManager._uapi_succeeded(payload)


def test_uapi_succeeded_rejects_error_envelopes():
    assert not CpanelBrowserMailboxManager._uapi_succeeded({"result": {"status": 0}})
    assert not CpanelBrowserMailboxManager._uapi_succeeded({"error": "not authenticated"})


def test_list_domain_email_addresses_includes_all_valid_domain_mailboxes(monkeypatch):
    manager = CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="example.test",
    )
    page = object()

    @contextmanager
    def attached_browser():
        yield None, None, [page]

    monkeypatch.setattr(manager, "_attached_browser", attached_browser)
    monkeypatch.setattr(manager, "_find_authenticated_page", lambda pages: (page, []))
    monkeypatch.setattr(
        manager,
        "_list_mailboxes",
        lambda authenticated_page: [
            {"email": "qa-one@example.test"},
            {"email": "owner@example.test"},
            {"email": "invalid address@example.test"},
            {"email": "outside@other.test"},
            {"email": "bad-envelope"},
        ],
    )

    assert manager.list_domain_email_addresses() == [
        "qa-one@example.test",
        "owner@example.test",
    ]


def test_list_domain_mailboxes_keeps_qa_prefix_filter(monkeypatch):
    manager = CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="example.test",
        prefix="qa",
    )
    monkeypatch.setattr(
        manager,
        "list_domain_email_addresses",
        lambda: ["owner@example.test", "qa-one@example.test"],
    )

    assert manager.list_domain_mailboxes() == ["qa-one@example.test"]



def test_create_five_manager_allows_empty_password_for_random_generation():
    manager = CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="teguhharits.com",
        mailbox_password="",
    )
    assert manager.mailbox_password == ""
    generated = manager._generate_mailbox_password()
    assert len(generated) >= 20
    assert any(char.islower() for char in generated)
    assert any(char.isupper() for char in generated)
    assert any(char.isdigit() for char in generated)


def test_create_five_manager_keeps_configured_shared_password():
    manager = CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="teguhharits.com",
        mailbox_password="Test-Shared-QA-Password-2026!",
    )
    assert manager.mailbox_password == "Test-Shared-QA-Password-2026!"


def test_reset_mailbox_passwords_rejects_other_domains():
    manager = CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="teguhharits.com",
        mailbox_password="temporary-test-password",
    )
    try:
        manager.reset_mailbox_passwords(["qa@example.test"])
    except Exception as exc:
        assert "domain" in str(exc).lower()
    else:
        raise AssertionError("Password reset must be restricted to the owned QA domain")



def test_oauth_target_allows_localhost_http():
    assert CpanelBrowserMailboxManager._validate_oauth_target_url(
        "http://localhost:3000/register"
    ) == "http://localhost:3000/register"


def test_oauth_target_rejects_remote_http():
    try:
        CpanelBrowserMailboxManager._validate_oauth_target_url(
            "http://example.com/register"
        )
    except Exception as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("Remote HTTP targets must be rejected")


def test_oauth_target_rejects_embedded_credentials():
    try:
        CpanelBrowserMailboxManager._validate_oauth_target_url(
            "https://user:pass@example.com/register"
        )
    except Exception as exc:
        assert "credentials" in str(exc).lower()
    else:
        raise AssertionError("Credentials in URLs must be rejected")
