from __future__ import annotations

from contextlib import contextmanager

import pytest

from simuru_research.providers.cpanel_browser import CpanelBrowserMailboxManager
from simuru_research.providers.mailbox import MailboxError


class FakeLocator:
    def __init__(self, page, selector: str) -> None:
        self.page = page
        self.selector = selector
        self.first = self

    def count(self) -> int:
        return 0 if self.selector == "[role='alert']" else 1

    def wait_for(self, *, state: str, timeout: int) -> None:
        assert state == "visible"

    def fill(self, value: str, *, timeout: int) -> None:
        self.page.filled.append((self.selector, value))

    def click(self, *, timeout: int) -> None:
        self.page.clicked.append(self.selector)

    def inner_text(self, *, timeout: int) -> str:
        return ""


class FakePage:
    def __init__(self) -> None:
        self.url = "https://staging.example.test/register"
        self.visited: list[str] = []
        self.filled: list[tuple[str, str]] = []
        self.clicked: list[str] = []

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.visited.append(url)

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        return None

    def wait_for_timeout(self, timeout: int) -> None:
        return None


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()

    def new_page(self) -> FakePage:
        return self.page


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self.context = context

    def new_context(self) -> FakeContext:
        return self.context


def manager() -> CpanelBrowserMailboxManager:
    return CpanelBrowserMailboxManager(
        cpanel_url="https://cpanel.example.test:2083",
        domain="teguhharits.com",
        prefix="qa",
    )


def test_email_fallback_submits_five_unique_qa_identities(monkeypatch):
    browser_manager = manager()
    context = FakeContext()

    @contextmanager
    def attached_browser():
        yield FakeBrowser(context), context, [context.page]

    monkeypatch.setattr(browser_manager, "_attached_browser", attached_browser)
    identities = [
        {
            "email": f"qa-batch1234-{index:02d}@teguhharits.com",
            "password": f"Local-QA-Password-{index:02d}!",
            "name": f"QA User {index:02d}",
        }
        for index in range(1, 6)
    ]
    selectors = {
        "name": "#full-name",
        "email": "#email",
        "password": "#password",
        "confirm_password": "#password-confirm",
        "submit": "form button[type=submit]",
    }

    results = browser_manager.run_email_registration_batch(
        "https://staging.example.test/register",
        selectors,
        identities,
    )

    assert len(results) == 5
    assert all(row["status"] == "submitted" for row in results)
    assert len(context.page.visited) == 5
    assert len(context.page.clicked) == 5
    assert len({row["email"] for row in results}) == 5


def test_email_fallback_rejects_non_qa_mailboxes_before_opening_browser():
    browser_manager = manager()
    identities = [
        {
            "email": f"someone-{index}@other.example",
            "password": "Local-QA-Password-123!",
        }
        for index in range(5)
    ]
    selectors = {"email": "#email", "password": "#password", "submit": "button"}

    with pytest.raises(MailboxError, match="generated QA mailboxes"):
        browser_manager.run_email_registration_batch(
            "https://staging.example.test/register",
            selectors,
            identities,
        )


def test_email_fallback_requires_exactly_five_identities():
    browser_manager = manager()
    with pytest.raises(MailboxError, match="exactly five"):
        browser_manager.run_email_registration_batch(
            "https://staging.example.test/register",
            {"email": "#email", "password": "#password", "submit": "button"},
            [],
        )
