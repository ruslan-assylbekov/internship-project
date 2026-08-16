"""Regression tests for app-level wiring: middleware, mounts, health, routers."""

import logging
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api import weather_router
from src.core.database.database_connect import get_session
from src.core.logging_config import KeyValueFormatter, request_id_var
from src.main import REQUEST_ID_HEADER, app, collection_paths


def test_weather_service_missing_key_is_a_request_error_not_an_import_error():
    """Settings used to be constructed at import time.

    A missing API_KEY made importing the app raise, which broke every test
    and any tooling that merely imported the module. It must now surface as
    a per-request 500 instead.
    """
    weather_router.get_settings.cache_clear()
    try:
        settings = weather_router.get_settings()
        original = settings.api_key
        settings.api_key = ""
        try:
            with TestClient(app) as client:
                response = client.get("/weather/Astana")
        finally:
            settings.api_key = original
    finally:
        weather_router.get_settings.cache_clear()

    assert response.status_code == 500
    assert response.json()["detail"] == "API_KEY is not configured"


def test_cors_does_not_combine_wildcard_origin_with_credentials():
    """Browsers reject Access-Control-Allow-Origin: * on credentialed requests."""
    with TestClient(app) as client:
        response = client.get("/books/", headers={"Origin": "http://example.com"})

    assert response.headers.get("access-control-allow-credentials") != "true"


def test_request_timing_header_is_present():
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert "request-process-time" in response.headers


def test_every_router_is_registered():
    paths = {route.path for route in app.routes}

    assert "/users/" in paths
    assert "/users/me" in paths
    assert "/books/" in paths
    assert "/weather/{city}" in paths
    assert "/auth/login" in paths
    assert "/auth/token" in paths
    assert "/borrowings/" in paths
    assert "/borrowings/borrow" in paths
    assert "/health" in paths


# --------------------------------------------------------------------------
# Request ids
# --------------------------------------------------------------------------

def test_a_request_id_is_generated_and_returned():
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.headers[REQUEST_ID_HEADER]


def test_an_inbound_request_id_is_honoured():
    """A trace started by a proxy or the caller must survive this hop."""
    with TestClient(app) as client:
        response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: "trace-me"})

    assert response.headers[REQUEST_ID_HEADER] == "trace-me"


def test_each_request_gets_its_own_id():
    with TestClient(app) as client:
        first = client.get("/openapi.json").headers[REQUEST_ID_HEADER]
        second = client.get("/openapi.json").headers[REQUEST_ID_HEADER]

    assert first != second


def test_the_request_log_carries_the_id_method_and_status(caplog):
    """The middleware used to print an unparseable line with no id at all."""
    with caplog.at_level(logging.INFO, logger="src.main"), TestClient(app) as client:
        client.get("/openapi.json", headers={REQUEST_ID_HEADER: "trace-me"})

    record = next(r for r in caplog.records if r.getMessage() == "request handled")
    assert record.request_id == "trace-me"
    assert record.method == "GET"
    assert record.path == "/openapi.json"
    assert record.status == 200


def test_the_request_id_context_is_reset_after_the_request():
    """A leaked contextvar would stamp the next request with the previous id."""
    with TestClient(app) as client:
        client.get("/openapi.json", headers={REQUEST_ID_HEADER: "trace-me"})

    assert request_id_var.get() == "-"


def test_log_lines_are_key_value_formatted():
    record = logging.LogRecord(
        name="src.main", level=logging.INFO, pathname=__file__, lineno=1,
        msg="request handled", args=None, exc_info=None,
    )
    record.status = 200
    record.request_id = "trace-me"

    line = KeyValueFormatter().format(record)

    assert 'msg="request handled"' in line
    assert "level=INFO" in line
    assert "status=200" in line
    assert "request_id=trace-me" in line


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

def test_health_is_ok_when_the_database_answers():
    db = MagicMock()
    app.dependency_overrides[get_session] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    # A probe that never touches the database only proves the process is up.
    db.execute.assert_called_once()


def test_health_is_503_when_the_database_is_unreachable():
    db = MagicMock()
    db.execute.side_effect = SQLAlchemyError("connection refused")
    app.dependency_overrides[get_session] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unreachable"}


def test_health_needs_no_token():
    """An orchestrator probing this endpoint has no credentials to offer."""
    db = MagicMock()
    app.dependency_overrides[get_session] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

def test_the_frontend_is_served_from_the_app_root():
    """Mounted so the page is same-origin with the API: no CORS, no hardcoded host."""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_static_assets_are_served():
    with TestClient(app) as client:
        response = client.get("/app.js")

    assert response.status_code == 200


def test_the_static_mount_does_not_shadow_the_api():
    """The mount is at "/" and matches anything, so it must be registered last."""
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_an_unknown_path_is_still_a_404():
    with TestClient(app) as client:
        response = client.get("/no-such-page")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# Trailing slashes
#
# Routes are declared as "/books/", and FastAPI answers "/books" with a 307 to
# it. The static mount at "/" matches everything, so without the redirect
# middleware "/books" reaches the file server and returns a bare 404 that reads
# as "no such endpoint".
# --------------------------------------------------------------------------

def test_a_collection_path_without_its_slash_redirects():
    with TestClient(app) as client:
        response = client.get("/books", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/books/"


def test_the_redirect_keeps_the_query_string():
    """Dropping it would silently discard the caller's search and paging."""
    with TestClient(app) as client:
        response = client.get("/books?q=dostoevsky&limit=5", follow_redirects=False)

    assert response.headers["location"] == "/books/?q=dostoevsky&limit=5"


def test_every_collection_route_is_covered():
    """Derived from the routing table, so a new router cannot be forgotten."""
    assert collection_paths() == {"/users", "/books", "/borrowings"}


def test_a_redirect_is_still_logged_and_carries_a_request_id():
    with TestClient(app) as client:
        response = client.get("/books", follow_redirects=False)

    assert response.headers[REQUEST_ID_HEADER]
