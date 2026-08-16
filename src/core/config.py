"""Application settings, resolved once per process.

Settings are read lazily through :func:`get_settings` rather than at import
time. Constructing ``Settings()`` while a module is being imported made the
whole app fail to import when ``.env`` was absent, which broke tooling and the
test suite; every field below therefore has a default and a missing value is
reported where it is used instead.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # weatherapi.com key, used by GET /weather/{city}. Empty means the weather
    # endpoint answers 500; the rest of the app is unaffected.
    api_key: str = ""

    # Signing key for access tokens. Empty means an ephemeral key is generated
    # for the process (see src.core.security.get_signing_key), so tokens stop
    # working across restarts -- fine for dev, not for anything shared.
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # How long a city's weather stays cached before the provider is called again.
    weather_cache_ttl_seconds: int = 300

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
