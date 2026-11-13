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

    with SimuruClient(
        api_key="test-api-key",
        base_url="https://simuru.com/api",
        transport=httpx.MockTransport(handler),
    ) as client:
        profile = client.get_profile()

    assert profile["name"] == "Test User"
    assert profile["status"] == "active"


def test_account_balance_and_catalog_read_endpoints() -> None:
    responses = {
        "/api/balance": {
            "success": True,
            "data": {"balance": 25000, "balance_formatted": "Rp 25.000"},
        },
        "/api/services": {
            "success": True,
            "data": [{"service_id": "whatsapp", "service_name": "WhatsApp"}],
        },
        "/api/countries": {
            "success": True,
            "data": [{"id": 7, "name": "Indonesia", "iso_code": "ID"}],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["X-API-KEY"] == "test-api-key"
        return httpx.Response(200, json=responses[request.url.path])

    with SimuruClient(
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        balance = client.get_balance()
        services = client.get_services()
        countries = client.get_countries()

    assert balance["balance"] == 25000
    assert services[0]["service_id"] == "whatsapp"
    assert countries[0]["iso_code"] == "ID"


def test_pricelist_sends_optional_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/pricelist"
        assert request.url.params["service_id"] == "whatsapp"
        assert request.url.params["country_id"] == "7"
        assert request.headers["Accept-Encoding"] == "gzip"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": [{"service_id": "whatsapp", "country_id": 7, "price": 500}],
                "meta": {"total": 1},
            },
        )

    with SimuruClient(
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.get_pricelist(service_id="whatsapp", country_id=7)

    assert result["data"][0]["price"] == 500
    assert result["meta"]["total"] == 1


def test_service_country_operators_offers_and_insights_paths() -> None:
    expected_paths = {
        "/api/services/whatsapp/countries",
        "/api/services/whatsapp/countries/7/operators",
        "/api/services/whatsapp/countries/7/offers",
        "/api/insights/countries",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path in expected_paths
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": (
                    []
                    if request.url.path.endswith("/countries")
                    and request.url.path == "/api/services/whatsapp/countries"
                    else {"supports_selection": True, "operators": []}
                    if request.url.path.endswith("/operators")
                    else {"supports_pricing": True, "options": []}
                    if request.url.path.endswith("/offers")
                    else {"window_hours": 24, "services": []}
                ),
                "ranking_note": None,
            },
        )

    with SimuruClient(
        api_key="test-api-key",
        transport=httpx.MockTransport(handler),
    ) as client:
        countries = client.get_service_countries("whatsapp")
        operators = client.get_operators("whatsapp", 7)
        offers = client.get_offers("whatsapp", 7)
        insights = client.get_country_insights()

    assert countries["data"] == []
    assert operators["supports_selection"] is True
    assert offers["supports_pricing"] is True
    assert insights["window_hours"] == 24


def test_rejects_non_official_api_host() -> None:
    with pytest.raises(ValueError):
        SimuruClient(
            api_key="test-api-key",
            base_url="https://example.com/api",
        )


def test_rejects_invalid_path_parameters() -> None:
    with SimuruClient(api_key="test-api-key") as client:
        with pytest.raises(ValueError):
            client.get_service_countries("../order/create")
        with pytest.raises(ValueError):
            client.get_operators("whatsapp", 0)


def test_reports_unsuccessful_api_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            401,
            json={"success": False, "message": "Invalid API key."},
        )
    )
    with SimuruClient(
        api_key="test-api-key",
        transport=transport,
    ) as client:
        with pytest.raises(SimuruAPIError, match="Invalid API key"):
            client.get_profile()
