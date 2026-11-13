from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse


class GoogleOAuthQAConfigError(ValueError):
    """Invalid local Google OAuth QA configuration."""


def validate_google_oauth_qa_config(config: dict[str, object]) -> dict[str, object]:
    project_name = str(config.get("project_name", "")).strip()
    client_id = str(config.get("client_id", "")).strip()
    redirect_uri = str(config.get("redirect_uri", "")).strip()
    emails_value = config.get("emails", [])
    if not project_name:
        raise GoogleOAuthQAConfigError("Google Cloud project name is required.")
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise GoogleOAuthQAConfigError("Enter a valid Google OAuth Client ID.")
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise GoogleOAuthQAConfigError("Redirect URI must be a complete HTTP(S) URL.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise GoogleOAuthQAConfigError("Remote redirect URIs must use HTTPS.")
    if not isinstance(emails_value, list) or len(emails_value) != 5:
        raise GoogleOAuthQAConfigError("Exactly five verified mailbox addresses are required.")
    emails = []
    for value in emails_value:
        email = str(value).strip().lower()
        if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
            raise GoogleOAuthQAConfigError(f"Invalid mailbox address: {email}")
        emails.append(email)
    if len(set(emails)) != 5:
        raise GoogleOAuthQAConfigError("Google OAuth QA emails must be unique.")
    return {
        "project_name": project_name,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "emails": emails,
        "scopes": ["openid", "email", "profile"],
        "test_users_confirmed": bool(config.get("test_users_confirmed", False)),
        "client_secret_configured": False,
    }


class GoogleOAuthQAConfigStore:
    """Persist non-secret OAuth test-user preparation metadata locally."""

    def __init__(self, path: str | Path = "data/google_oauth_qa.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, config: dict[str, object]) -> dict[str, object]:
        clean = validate_google_oauth_qa_config(config)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return clean

    def load(self) -> dict[str, object] | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GoogleOAuthQAConfigError("Local OAuth QA configuration is invalid.") from exc
        if not isinstance(data, dict):
            raise GoogleOAuthQAConfigError("Local OAuth QA configuration must be an object.")
        return data
