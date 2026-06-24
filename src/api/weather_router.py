from fastapi import APIRouter, Depends
from src.services.weather_service import WeatherService
from pydantic_settings import BaseSettings, SettingsConfigDict
from src.schemas.user_schemas import WeatherResponse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    api_key: str

settings = Settings()
router = APIRouter(prefix="/weather", tags=["Weather"])

def get_weather_service():
    return WeatherService(settings.api_key)

@router.get("/{city}", response_model=WeatherResponse)
def get_weather(city: str, service: WeatherService = Depends(get_weather_service)):
    return service.get_forecast(city)
