from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


class WebsiteProfileError(ValueError):
    """Invalid website profile configuration."""


class WebsiteProfileStore:
    """Persist website automation profiles locally as JSON."""

    def __init__(self, path: str | Path = "data/website_profiles.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WebsiteProfileError(
                "Website profile file is unreadable or invalid JSON."
            ) from exc
        if not isinstance(payload, list):
            raise WebsiteProfileError("Website profile file must contain a JSON list.")
        return [item for item in payload if isinstance(item, dict)]

    def save(self, profile: dict[str, object]) -> None:
        validated = validate_profile(profile)
        profiles = self.list_profiles()
        profiles = [
            item for item in profiles
            if str(item.get("name", "")).casefold() != str(validated["name"]).casefold()
        ]
        profiles.append(validated)
        self._write(profiles)

    def delete(self, name: str) -> bool:
        profiles = self.list_profiles()
        remaining = [item for item in profiles if str(item.get("name", "")) != name]
        if len(remaining) == len(profiles):
            return False
        self._write(remaining)
        return True

    def _write(self, profiles: list[dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(profiles, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def validate_profile(profile: dict[str, object]) -> dict[str, object]:
    name = str(profile.get("name", "")).strip()
    base_url = str(profile.get("base_url", "")).strip().rstrip("/")
    register_path = str(profile.get("register_path", "/register")).strip()
    auth_method = str(profile.get("auth_method", "email_password"))
    if not name:
        raise WebsiteProfileError("Website name is required.")
    if len(name) > 80:
        raise WebsiteProfileError("Website name must be 80 characters or fewer.")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise WebsiteProfileError("Base URL must be a valid http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise WebsiteProfileError("Do not put credentials in the website URL.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise WebsiteProfileError("Non-local website profiles must use HTTPS.")
    if not register_path.startswith("/") or register_path.startswith("//"):
        raise WebsiteProfileError("Registration path must start with one slash.")
    if auth_method not in {"email_password", "google_oauth", "email_and_google"}:
        raise WebsiteProfileError("Unsupported authentication method.")
    selectors = profile.get("selectors", {})
    if not isinstance(selectors, dict):
        raise WebsiteProfileError("Selectors must be a mapping.")
    clean_selectors: dict[str, str] = {}
    for key in ("name", "email", "password", "confirm_password", "submit"):
        value = str(selectors.get(key, "")).strip()
        if len(value) > 300:
            raise WebsiteProfileError(f"Selector '{key}' is too long.")
        clean_selectors[key] = value
    if auth_method in {"email_password", "email_and_google"}:
        required = ("email", "password", "submit")
        if any(not clean_selectors[key] for key in required):
            raise WebsiteProfileError("Email, password, and submit selectors are required.")
    return {
        "name": name,
        "base_url": base_url,
        "register_path": register_path,
        "auth_method": auth_method,
        "google_oauth_enabled": bool(profile.get("google_oauth_enabled", False)),
        "selectors": clean_selectors,
        "authorized_for_testing": bool(profile.get("authorized_for_testing", False)),
    }


def profile_registration_url(profile: dict[str, object]) -> str:
    return f"{str(profile['base_url']).rstrip('/')}{profile['register_path']}"
