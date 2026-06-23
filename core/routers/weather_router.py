from fastapi import APIRouter
from core.services.weather_service import WeatherService
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    class Config:
        env_file = ".env"

settings = Settings()
router = APIRouter(prefix="/weather", tags=["Weather"])

@router.get("/{city}")
def get_weather(city: str):
    service = WeatherService(settings.api_key)
    return service.get_forecast(city)