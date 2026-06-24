from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from core.backend.main import app
from src.api.weather_router import get_weather_service
from src.services.weather_service import WeatherService


def test_weather_service_maps_provider_response():
    with patch("src.services.weather_service.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "location": {"name": "London"},
            "current": {
                "temp_c": 20,
                "feelslike_c": 19,
                "condition": {"text": "Sunny"},
            },
        }

        service = WeatherService(api_key="fake_key")
        result = service.get_forecast("London")

    assert result["city"] == "London"
    assert result["temperature"] == 20
    mock_get.assert_called_once()


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
