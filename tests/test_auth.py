from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

from src.api.dependencies import get_user_service
from src.core.security import create_access_token, get_signing_key, hash_password
from src.main import app


def make_user():
    return {
        "id": 1,
        "email": "ruslan@example.com",
        "firstname": "Ruslan",
        "lastname": "Assylbekov",
        "created": datetime.now(UTC).isoformat(),
    }


def make_user_object():
    """What the repository actually returns: an object with attributes.

    ``/auth/login`` reads ``user.id`` to sign the token, which a dict cannot
    satisfy.
    """
    return SimpleNamespace(
        id=1,
        email="ruslan@example.com",
        firstname="Ruslan",
        lastname="Assylbekov",
        password=hash_password("correct horse battery"),
        created=datetime.now(UTC),
        borrowings=[],
    )


def post_login(service, password="correct horse battery"):
    app.dependency_overrides[get_user_service] = lambda: service
    try:
        with TestClient(app) as client:
            return client.post(
                "/auth/login",
                json={"email": "ruslan@example.com", "password": password},
            )
    finally:
        app.dependency_overrides.clear()


def test_login_returns_a_token_and_the_user():
    service = MagicMock()
    service.authenticate.return_value = make_user_object()

    response = post_login(service)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "ruslan@example.com"
    service.authenticate.assert_called_once_with(
        "ruslan@example.com", "correct horse battery"
    )


def test_login_token_identifies_the_user_that_logged_in():
    service = MagicMock()
    service.authenticate.return_value = make_user_object()

    response = post_login(service)

    payload = jwt.decode(
        response.json()["access_token"], get_signing_key(), algorithms=["HS256"]
    )
    assert payload["sub"] == "1"
    assert "exp" in payload


def test_login_never_returns_the_password_field():
    """Checked against the whole body: the hash must not leak from any level of
    the response, not just the top one.
    """
    service = MagicMock()
    service.authenticate.return_value = make_user_object()

    response = post_login(service)

    assert "password" not in response.text
    assert "$2b$" not in response.text


def test_login_returns_401_on_bad_credentials():
    service = MagicMock()
    service.authenticate.return_value = None

    response = post_login(service, password="wrong")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_rejects_malformed_email_before_service_call():
    service = MagicMock()
    app.dependency_overrides[get_user_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/login", json={"email": "not-an-email", "password": "x"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.authenticate.assert_not_called()


def test_token_endpoint_accepts_the_oauth2_form():
    """The /docs Authorize button posts a form with 'username', not JSON."""
    service = MagicMock()
    service.authenticate.return_value = make_user_object()
    app.dependency_overrides[get_user_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/token",
                data={"username": "ruslan@example.com", "password": "correct horse battery"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    service.authenticate.assert_called_once_with(
        "ruslan@example.com", "correct horse battery"
    )


def test_token_endpoint_returns_401_with_a_www_authenticate_header():
    service = MagicMock()
    service.authenticate.return_value = None
    app.dependency_overrides[get_user_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/token", data={"username": "ruslan@example.com", "password": "wrong"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


# --------------------------------------------------------------------------
# get_current_user: exercised through a protected route with real tokens, so
# the whole chain (header parsing, signature check, user lookup) is covered.
# --------------------------------------------------------------------------

def call_me(headers=None, service=None):
    if service is None:
        service = MagicMock()
        service.get_user_by_id.return_value = make_user_object()
    app.dependency_overrides[get_user_service] = lambda: service

    try:
        with TestClient(app) as client:
            return client.get("/auth/me", headers=headers or {}), service
    finally:
        app.dependency_overrides.clear()


def test_a_valid_token_resolves_to_its_user():
    response, service = call_me({"Authorization": f"Bearer {create_access_token(1)}"})

    assert response.status_code == 200
    assert response.json()["email"] == "ruslan@example.com"
    # Looked up per request rather than trusted from the token payload.
    service.get_user_by_id.assert_called_once_with(1)


def test_request_without_a_token_is_rejected():
    response, service = call_me()

    assert response.status_code == 401
    service.get_user_by_id.assert_not_called()


def test_expired_token_is_rejected():
    expired = create_access_token(1, expires_delta=timedelta(seconds=-1))

    response, service = call_me({"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
    service.get_user_by_id.assert_not_called()


def test_token_signed_with_another_key_is_rejected():
    """The signature is what stops a client from minting its own tokens.

    The decoy key is padded to 32 bytes because PyJWT warns below that, and the
    suite turns warnings into errors.
    """
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "not-the-signing-key" + "x" * 32,
        algorithm="HS256",
    )

    response, _ = call_me({"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_token_with_a_non_numeric_subject_is_rejected():
    response, service = call_me({"Authorization": f"Bearer {create_access_token('abc')}"})

    assert response.status_code == 401
    service.get_user_by_id.assert_not_called()


def test_token_for_a_deleted_user_is_rejected():
    """Tokens outlive the rows they name; the lookup is what closes that gap."""
    service = MagicMock()
    service.get_user_by_id.return_value = None

    response, _ = call_me({"Authorization": f"Bearer {create_access_token(99)}"}, service)

    assert response.status_code == 401


def test_rejection_does_not_say_which_part_failed():
    """Expired, forged and unknown-user must be indistinguishable, or the
    endpoint becomes an oracle for which accounts exist.
    """
    unknown = MagicMock()
    unknown.get_user_by_id.return_value = None

    expired_response, _ = call_me(
        {"Authorization": f"Bearer {create_access_token(1, timedelta(seconds=-1))}"}
    )
    unknown_response, _ = call_me(
        {"Authorization": f"Bearer {create_access_token(99)}"}, unknown
    )

    assert expired_response.json() == unknown_response.json()
