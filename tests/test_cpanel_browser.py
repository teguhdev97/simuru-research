from __future__ import annotations

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
