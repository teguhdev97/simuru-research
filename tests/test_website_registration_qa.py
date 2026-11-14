from __future__ import annotations

import pytest

from simuru_research.engine.website_registration_qa import (
    WebsiteRegistrationQAError,
    validate_registration_target,
)


def test_localhost_registration_target_is_allowed(monkeypatch):
    monkeypatch.delenv("WEBSITE_QA_ALLOWED_HOSTS", raising=False)
    assert validate_registration_target("http://localhost:8000/register") == (
        "http://localhost:8000/register"
    )


def test_allowlisted_staging_host_requires_https(monkeypatch):
    monkeypatch.setenv("WEBSITE_QA_ALLOWED_HOSTS", "localhost,staging.example.test")
    assert validate_registration_target("https://staging.example.test/register").startswith(
        "https://"
    )
    with pytest.raises(WebsiteRegistrationQAError, match="HTTPS"):
        validate_registration_target("http://staging.example.test/register")


@pytest.mark.parametrize(
    "url",
    [
        "https://santrikoding.com/register",
        "https://www.instagram.com/accounts/emailsignup/",
        "https://evil.example/register",
        "file:///etc/passwd",
        "https://user:password@localhost/register",
    ],
)
def test_unapproved_or_unsafe_registration_targets_are_rejected(monkeypatch, url):
    monkeypatch.delenv("WEBSITE_QA_ALLOWED_HOSTS", raising=False)
    with pytest.raises(WebsiteRegistrationQAError):
        validate_registration_target(url)
