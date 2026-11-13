from __future__ import annotations

import json

import pytest

from simuru_research.config.website_profiles import (
    WebsiteProfileError,
    WebsiteProfileStore,
    profile_registration_url,
    validate_profile,
)


def sample_profile(**overrides):
    profile = {
        "name": "Local Demo",
        "base_url": "http://localhost:3000",
        "register_path": "/register",
        "auth_method": "email_password",
        "google_oauth_enabled": True,
        "selectors": {
            "name": "input[name=name]",
            "email": "input[name=email]",
            "password": "input[name=password]",
            "confirm_password": "",
            "submit": "button[type=submit]",
        },
        "authorized_for_testing": True,
    }
    profile.update(overrides)
    return profile


def test_validate_profile_and_registration_url():
    profile = validate_profile(sample_profile())
    assert profile_registration_url(profile) == "http://localhost:3000/register"


def test_rejects_non_https_remote_site():
    with pytest.raises(WebsiteProfileError, match="HTTPS"):
        validate_profile(sample_profile(base_url="http://example.com"))


def test_rejects_missing_required_selectors():
    with pytest.raises(WebsiteProfileError, match="selectors"):
        validate_profile(sample_profile(selectors={"email": "", "password": "", "submit": ""}))


def test_store_upserts_and_deletes(tmp_path):
    store = WebsiteProfileStore(tmp_path / "profiles.json")
    store.save(sample_profile())
    store.save(sample_profile(base_url="http://localhost:4000"))
    profiles = store.list_profiles()
    assert len(profiles) == 1
    assert profiles[0]["base_url"] == "http://localhost:4000"
    assert store.delete("Local Demo")
    assert store.list_profiles() == []
    assert json.loads((tmp_path / "profiles.json").read_text()) == []
