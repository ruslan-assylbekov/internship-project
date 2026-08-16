import time

import requests


class WeatherUnavailable(Exception):
    """The weather provider could not be reached or returned something unusable."""


class TTLCache:
    """Smallest cache that fits: a dict with per-entry expiry.

    ``functools.lru_cache`` cannot expire entries, and the provider's readings
    go stale, so a hand-rolled TTL is the honest option. Not thread-safe by
    design -- a torn read costs one redundant upstream call, and locking every
    lookup to avoid that is a worse trade.
    """

    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, dict]] = {}

    def get(self, key: str) -> dict | None:
        entry = self._entries.get(key)
        if entry is None:
            return None

        stored_at, value = entry
        # monotonic, so a system clock change cannot freeze entries forever.
        if time.monotonic() - stored_at >= self.ttl_seconds:
            self._entries.pop(key, None)
            return None
        return value

    def set(self, key: str, value: dict) -> None:
        if self.ttl_seconds > 0:
            self._entries[key] = (time.monotonic(), value)

    def clear(self) -> None:
        self._entries.clear()


class WeatherService:
    def __init__(self, api_key: str, cache: TTLCache | None = None):
        self.api_key = api_key
        self.url = "https://api.weatherapi.com/v1/current.json"
        # A private cache unless one is injected. The app injects a shared
        # instance so all requests benefit; a bare WeatherService (as built in
        # unit tests) stays isolated and never returns another test's reading.
        self.cache = cache if cache is not None else TTLCache(0)

    def get_forecast(self, city: str):
        key = city.strip().lower()

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        try:
            response = requests.get(
                self.url,
                params={"key": self.api_key, "q": city},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise WeatherUnavailable(f"weather lookup for {city!r} failed: {exc}") from exc

        try:
            forecast = {
                "city": data["location"]["name"],
                "temperature": data["current"]["temp_c"],
                "feeling": data["current"]["feelslike_c"],
                "clouds": data["current"]["condition"]["text"],
            }
        except (KeyError, TypeError) as exc:
            raise WeatherUnavailable(
                f"unexpected provider response for {city!r}"
            ) from exc

        # Only successes are cached: a provider outage should not be remembered.
        self.cache.set(key, forecast)
        return forecast
