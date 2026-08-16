"""Password hashing and access-token signing."""

import datetime
import logging
import secrets
from functools import lru_cache

import bcrypt
import jwt

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# bcrypt truncates at 72 bytes and raises above it; schemas cap input to match.
MAX_PASSWORD_BYTES = 72

# RFC 7518 puts the floor for HMAC-SHA256 at the hash length; PyJWT warns below
# it, and a short key is the one configuration mistake that silently weakens
# every token the app issues.
MIN_SECRET_KEY_BYTES = 32


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Check a password against a stored bcrypt hash.

    Returns False rather than raising when the stored value is not a bcrypt
    hash -- rows written before hashing was introduced hold plaintext, and
    those accounts must fail closed instead of erroring.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


@lru_cache
def _ephemeral_signing_key() -> str:
    """A per-process key, used only when SECRET_KEY is unset.

    Shipping a hardcoded fallback would mean anyone could mint tokens for a
    deployment that forgot to configure one, so an unset key degrades to
    "tokens do not survive a restart" instead.
    """
    logger.warning(
        "SECRET_KEY is not set: generated an ephemeral signing key, so issued "
        "tokens become invalid when this process restarts. Set SECRET_KEY in "
        ".env for stable sessions."
    )
    return secrets.token_urlsafe(32)


def get_signing_key() -> str:
    configured = get_settings().secret_key
    if not configured:
        return _ephemeral_signing_key()
    if len(configured.encode("utf-8")) < MIN_SECRET_KEY_BYTES:
        _warn_short_secret_key(len(configured))
    return configured


@lru_cache
def _warn_short_secret_key(length: int) -> None:
    """Warned once per distinct length, not once per token signed."""
    logger.warning(
        "SECRET_KEY is shorter than the recommended minimum, which weakens "
        "every token signed with it",
        extra={"length": length, "minimum": MIN_SECRET_KEY_BYTES},
    )


def create_access_token(
    subject: str | int,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """Sign a JWT whose ``sub`` claim is the user id."""
    settings = get_settings()
    now = datetime.datetime.now(datetime.UTC)
    expires = now + (
        expires_delta
        if expires_delta is not None
        else datetime.timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "iat": now, "exp": expires}
    return jwt.encode(payload, get_signing_key(), algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if it is invalid, expired or forged.

    Mirrors ``verify_password``: callers get a falsy result to turn into a 401
    rather than an exception to catch at every call site.
    """
    try:
        return jwt.decode(
            token,
            get_signing_key(),
            algorithms=[get_settings().algorithm],
        )
    except jwt.PyJWTError:
        return None
