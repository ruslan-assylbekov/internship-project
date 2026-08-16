from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from src.core.config import Settings, get_settings
from src.schemas.weather_schemas import WeatherResponse
from src.services.weather_service import TTLCache, WeatherService, WeatherUnavailable

# Settings and get_settings used to be defined here; they now live in
# src.core.config because tokens and logging need them too. Re-exported so
# existing importers (and tests patching weather_router.get_settings) still
# refer to the same objects.
__all__ = ["router", "Settings", "get_settings", "get_weather_cache", "get_weather_service"]

router = APIRouter(prefix="/weather", tags=["Weather"])


@lru_cache
def get_weather_cache() -> TTLCache:
    """One cache for the whole process.

    A fresh WeatherService is built per request, so the cache cannot live on the
    instance and still be useful. lru_cache defers reading the TTL setting until
    first use, keeping import free of configuration.
    """
    return TTLCache(get_settings().weather_cache_ttl_seconds)


def get_weather_service() -> WeatherService:
    api_key = get_settings().api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="API_KEY is not configured")
    return WeatherService(api_key, cache=get_weather_cache())


@router.get("/{city}", response_model=WeatherResponse)
def get_weather(city: str, service: WeatherService = Depends(get_weather_service)):
    try:
        return service.get_forecast(city)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
