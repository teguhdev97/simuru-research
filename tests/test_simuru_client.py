from __future__ import annotations

import httpx
import pytest

from simuru_research.providers.simuru_client import SimuruAPIError, SimuruClient


def test_profile_uses_api_key_header_and_read_only_path() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/profile"
        assert request.headers["X-API-KEY"] == "test-api-key"
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "OK",
                "data": {"name": "Test User", "status": "active"},
            },
        )

    transport = httpx.MockTransport(handler)
    with SimuruClient(
        api_key="test-api-key",
        base_url="https://simuru.com/api",
        transport=transport,
    ) as client:
        profile = client.get_profile()

    assert profile["name"] == "Test User"
    assert profile["status"] == "active"


def test_rejects_non_official_api_host() -> None:
    with pytest.raises(ValueError):
        SimuruClient(
            api_key="test-api-key",
            base_url="https://example.com/api",
        )


def test_reports_unsuccessful_api_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"success": False, "message": "Invalid API key."},
        )
    )
    with SimuruClient(
        api_key="test-api-key",
        transport=transport,
    ) as client:
        with pytest.raises(SimuruAPIError, match="Invalid API key"):
            client.get_profile()
