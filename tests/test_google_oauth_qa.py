from __future__ import annotations

import pytest

from simuru_research.config.google_oauth_qa import (
    GoogleOAuthQAConfigError,
    GoogleOAuthQAConfigStore,
    validate_google_oauth_qa_config,
)


def make_config(**overrides):
    config = {
        "project_name": "SIMURU OAuth QA",
        "client_id": "123-example.apps.googleusercontent.com",
        "redirect_uri": "http://localhost:8000/auth/google/callback",
        "emails": [f"qa{i}@teguhharits.com" for i in range(1, 6)],
    }
    config.update(overrides)
    return config


def test_validate_google_oauth_test_user_config():
    clean = validate_google_oauth_qa_config(make_config())
    assert len(clean["emails"]) == 5
    assert clean["scopes"] == ["openid", "email", "profile"]
    assert clean["client_secret_configured"] is False


def test_rejects_duplicate_emails():
    with pytest.raises(GoogleOAuthQAConfigError, match="unique"):
        validate_google_oauth_qa_config(
            make_config(emails=["same@teguhharits.com"] * 5)
        )


def test_rejects_non_https_remote_redirect():
    with pytest.raises(GoogleOAuthQAConfigError, match="HTTPS"):
        validate_google_oauth_qa_config(
            make_config(redirect_uri="http://example.com/callback")
        )


def test_store_persists_non_secret_config(tmp_path):
    store = GoogleOAuthQAConfigStore(tmp_path / "oauth.json")
    saved = store.save(make_config())
    loaded = store.load()
    assert loaded == saved
    assert "client_secret" not in loaded
