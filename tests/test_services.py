import pytest
from unittest.mock import patch
from core.services.weather_service import WeatherService

@patch("requests.get")
def test_weather_service_logic(mock_get):
    mock_get.return_value.json.return_value = {
        "location": {"name": "London"},
        "current": {"temp_c": 20, "feelslike_c": 19, "condition": {"text": "Sunny"}},
    }
    mock_get.return_value.status_code = 200

    service = WeatherService(api_key="fake_key")
    result = service.get_forecast("London")

    assert result["city"] == "London"
    assert result["temperature"] == 20
