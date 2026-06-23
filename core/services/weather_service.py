import requests

class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "http://api.weatherapi.com/v1/forecast.json"

    def get_forecast(self, city: str):
        params = {
            "key": self.api_key,
            "q": city,
        }
        response = requests.get(self.url, params=params)
        data = response.json()
        return {
            "city": data["location"]["name"],
            "temperature": data["current"]["temp_c"],
        }