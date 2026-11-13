from __future__ import annotations

import pytest

from simuru_research.engine.browser_form_qa import _validate_target_url
from simuru_research.engine.browser_session_qa import (
    _captcha_may_be_present,
    run_sequential_browser_sessions,
)


def test_localhost_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BROWSER_QA_ALLOWED_HOSTS", raising=False)
    assert _validate_target_url("http://127.0.0.1:8000/register") == (
        "http://127.0.0.1:8000/register"
    )


def test_custom_staging_host_can_be_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BROWSER_QA_ALLOWED_HOSTS", "localhost,staging.example.org")
    assert _validate_target_url("https://staging.example.org/register").startswith("https://")


@pytest.mark.parametrize(
    "url",
    [
        "https://login.yahoo.com/account/create",
        "https://www.instagram.com/accounts/emailsignup/",
        "https://evil.example/register",
        "file:///etc/passwd",
        "https://user:password@localhost/register",
    ],
)
def test_external_or_unsafe_targets_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
) -> None:
    monkeypatch.delenv("BROWSER_QA_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError):
        _validate_target_url(url)


def test_session_count_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BROWSER_QA_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError, match="sessions must be between"):
        run_sequential_browser_sessions("http://localhost/register", sessions=21)


def test_timeout_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BROWSER_QA_ALLOWED_HOSTS", raising=False)
    with pytest.raises(ValueError, match="timeout_seconds"):
        run_sequential_browser_sessions("http://localhost/register", timeout_seconds=0)


class FakeDriver:
    def __init__(self, found: bool) -> None:
        self.found = found

    def find_elements(self, _by: str, selector: str) -> list[str]:
        return ["challenge"] if self.found and "captcha" in selector else []


def test_captcha_hint_when_matching_element_exists() -> None:
    assert _captcha_may_be_present(FakeDriver(found=True)) is True


def test_no_captcha_hint_when_no_matching_element_exists() -> None:
    assert _captcha_may_be_present(FakeDriver(found=False)) is False
