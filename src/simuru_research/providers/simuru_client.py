from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx


class SimuruAPIError(RuntimeError):
    """Raised when a Simuru API request fails."""


class SimuruClient:
    """Read-only client for the documented SIMURU account and catalog endpoints."""

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
            headers={
                "X-API-KEY": api_key.strip(),
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            timeout=timeout,
            transport=transport,
        )

    def get_profile(self) -> dict[str, Any]:
        return self._get_data_object("profile")

    def get_balance(self) -> dict[str, Any]:
        return self._get_data_object("balance")

    def get_services(self) -> list[dict[str, Any]]:
        return self._get_data_list("services")

    def get_countries(self) -> list[dict[str, Any]]:
        return self._get_data_list("countries")

    def get_pricelist(
        self,
        *,
        service_id: str | int | None = None,
        country_id: int | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {}
        if service_id is not None:
            params["service_id"] = _service_segment(service_id)
        if country_id is not None:
            params["country_id"] = _positive_id(country_id, "country_id")

        payload = self._get_payload("pricelist", params=params or None)
        if not isinstance(payload.get("data"), list):
            raise SimuruAPIError("The pricelist response did not contain a list in 'data'.")
        return payload

    def get_service_countries(self, service_id: str | int) -> dict[str, Any]:
        service = _service_segment(service_id)
        payload = self._get_payload(f"services/{service}/countries")
        if not isinstance(payload.get("data"), list):
            raise SimuruAPIError("The service-country response did not contain a list in 'data'.")
        return payload

    def get_operators(
        self,
        service_id: str | int,
        country_id: int,
    ) -> dict[str, Any]:
        service = _service_segment(service_id)
        country = _positive_id(country_id, "country_id")
        return self._get_data_object(
            f"services/{service}/countries/{country}/operators"
        )

    def get_offers(
        self,
        service_id: str | int,
        country_id: int,
    ) -> dict[str, Any]:
        service = _service_segment(service_id)
        country = _positive_id(country_id, "country_id")
        return self._get_data_object(
            f"services/{service}/countries/{country}/offers"
        )

    def get_country_insights(self) -> dict[str, Any]:
        return self._get_data_object("insights/countries")

    def _get_data_object(self, path: str) -> dict[str, Any]:
        data = self._get_payload(path).get("data")
        if not isinstance(data, dict):
            raise SimuruAPIError(f"The {path} response did not contain an object in 'data'.")
        return data

    def _get_data_list(self, path: str) -> list[dict[str, Any]]:
        data = self._get_payload(path).get("data")
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise SimuruAPIError(f"The {path} response did not contain a list of objects.")
        return data

    def _get_payload(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise SimuruAPIError(f"Unable to connect to the SIMURU {path} endpoint.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise SimuruAPIError(f"The SIMURU {path} endpoint returned invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise SimuruAPIError(f"The SIMURU {path} endpoint returned an invalid response.")

        if not response.is_success or payload.get("success") is not True:
            message = payload.get("message", f"HTTP {response.status_code}")
            raise SimuruAPIError(str(message))

        return payload

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SimuruClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _service_segment(value: str | int) -> str:
    segment = str(value).strip()
    if not segment or re.fullmatch(r"[A-Za-z0-9_-]+", segment) is None:
        raise ValueError("service_id must be a numeric ID or an alphanumeric service slug.")
    return segment


def _positive_id(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value
