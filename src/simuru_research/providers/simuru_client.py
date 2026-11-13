from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class SimuruAPIError(RuntimeError):
    """Raised when the read-only Simuru profile request fails."""


class SimuruClient:
    """Minimal read-only client. Only GET /profile is intentionally exposed."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://simuru.com/api",
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Simuru API key is required.")

        parsed = urlparse(base_url)
        if parsed.scheme != "https" or parsed.hostname != "simuru.com":
            raise ValueError("Only the official https://simuru.com API host is allowed.")

        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/",
            headers={"X-API-KEY": api_key.strip(), "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    def get_profile(self) -> dict[str, Any]:
        try:
            response = self._client.get("profile")
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SimuruAPIError("Unable to read the Simuru profile endpoint.") from exc

        if not isinstance(payload, dict) or payload.get("success") is not True:
            message = (
                payload.get("message", "Unexpected API response.")
                if isinstance(payload, dict)
                else "Invalid JSON response."
            )
            raise SimuruAPIError(str(message))

        data = payload.get("data")
        if not isinstance(data, dict):
            raise SimuruAPIError("The profile response did not contain an object in 'data'.")
        return data

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SimuruClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
