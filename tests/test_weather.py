from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from src.api.weather_router import get_weather_service
from src.main import app
from src.services.weather_service import TTLCache, WeatherService, WeatherUnavailable

PROVIDER_PAYLOAD = {
    "location": {"name": "London"},
    "current": {
        "temp_c": 20,
        "feelslike_c": 19,
        "condition": {"text": "Sunny"},
    },
}


def test_weather_service_maps_provider_response():
    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        service = WeatherService(api_key="fake_key")
        result = service.get_forecast("London")

    assert result["city"] == "London"
    assert result["temperature"] == 20
    mock_get.assert_called_once()


def test_weather_service_uses_https_and_a_timeout():
    """The API key travels in the query string, so the request must not be plaintext."""
    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        WeatherService(api_key="fake_key").get_forecast("London")

    url = mock_get.call_args.args[0]
    assert url.startswith("https://")
    assert mock_get.call_args.kwargs["timeout"] > 0


def test_weather_service_wraps_transport_errors():
    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(WeatherUnavailable):
            WeatherService(api_key="fake_key").get_forecast("London")


def test_weather_service_wraps_unexpected_payload():
    """An unknown city returns a body with no 'location' key rather than an error."""
    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {"error": {"code": 1006}}

        with pytest.raises(WeatherUnavailable):
            WeatherService(api_key="fake_key").get_forecast("Nowhereville")


def test_weather_api_uses_mocked_service():
    service = MagicMock()
    service.get_forecast.return_value = {
        "city": "Astana",
        "temperature": 25,
        "feeling": 24,
        "clouds": "Clear",
    }
    app.dependency_overrides[get_weather_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/weather/Astana")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["city"] == "Astana"
    service.get_forecast.assert_called_once_with("Astana")


def test_weather_api_returns_502_when_provider_fails():
    service = MagicMock()
    service.get_forecast.side_effect = WeatherUnavailable("provider down")
    app.dependency_overrides[get_weather_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/weather/Astana")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502


# --------------------------------------------------------------------------
# Caching: the provider rate-limits, and repeated lookups of one city were
# hitting it every time.
# --------------------------------------------------------------------------

def test_a_repeat_lookup_within_the_ttl_does_not_call_the_provider():
    service = WeatherService(api_key="fake_key", cache=TTLCache(60))

    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        first = service.get_forecast("London")
        second = service.get_forecast("London")

    assert first == second
    mock_get.assert_called_once()


def test_the_cache_key_ignores_case_and_padding():
    """A city is the same city whether it arrives as "london" or " London "."""
    service = WeatherService(api_key="fake_key", cache=TTLCache(60))

    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        service.get_forecast("London")
        service.get_forecast("  london  ")

    mock_get.assert_called_once()


def test_different_cities_are_cached_separately():
    service = WeatherService(api_key="fake_key", cache=TTLCache(60))

    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        service.get_forecast("London")
        service.get_forecast("Astana")

    assert mock_get.call_count == 2


def test_a_provider_failure_is_not_cached():
    """Caching an outage would keep serving the failure after it cleared."""
    cache = TTLCache(60)
    service = WeatherService(api_key="fake_key", cache=cache)

    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(WeatherUnavailable):
            service.get_forecast("London")

    assert cache.get("london") is None


def test_a_bare_service_does_not_cache():
    """Unit tests build WeatherService directly; a shared cache would leak one
    test's reading into another's assertions.
    """
    service = WeatherService(api_key="fake_key")

    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = PROVIDER_PAYLOAD

        service.get_forecast("London")
        service.get_forecast("London")

    assert mock_get.call_count == 2


def test_ttl_cache_returns_a_stored_value():
    cache = TTLCache(60)
    cache.set("london", {"city": "London"})

    assert cache.get("london") == {"city": "London"}


def test_ttl_cache_expires_a_stale_entry():
    cache = TTLCache(60)

    with patch("src.services.weather_service.time.monotonic", return_value=1000.0):
        cache.set("london", {"city": "London"})
        assert cache.get("london") is not None

    with patch("src.services.weather_service.time.monotonic", return_value=1061.0):
        assert cache.get("london") is None


def test_ttl_cache_misses_an_unknown_key():
    assert TTLCache(60).get("nowhere") is None


def test_a_zero_ttl_disables_caching():
    """Setting WEATHER_CACHE_TTL_SECONDS=0 must turn the cache off, not make
    entries live forever.
    """
    cache = TTLCache(0)
    cache.set("london", {"city": "London"})

    assert cache.get("london") is None
