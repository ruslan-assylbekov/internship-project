import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from src.api import (
    auth_router,
    book_router,
    borrowing_router,
    health_router,
    user_router,
    weather_router,
)
from src.core.logging_config import configure_logging, request_id_var

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Library API",
    description="Users, books, borrowings and weather lookup.",
    version="0.1.0",
)

REQUEST_ID_HEADER = "X-Request-ID"

# Filled on first use rather than at import: the routers are not registered yet
# at this point in the module.
_collection_paths: frozenset[str] | None = None


def collection_paths() -> frozenset[str]:
    """Slash-less forms of every route declared with a trailing slash.

    Derived from the routing table instead of a hand-kept list, so adding a
    router cannot leave this behind.
    """
    global _collection_paths
    if _collection_paths is None:
        _collection_paths = frozenset(
            route.path.rstrip("/")
            for route in app.routes
            if isinstance(route, APIRoute) and route.path.endswith("/") and route.path != "/"
        )
    return _collection_paths


# The frontend is served from this app (mounted below), but it is also opened
# straight from disk during development, which counts as a null/file origin.
# allow_credentials must stay False: browsers reject a wildcard origin combined
# with credentialed requests, and the token travels in the Authorization header
# rather than a cookie, so nothing here needs credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER, "request-process-time"],
)

@app.middleware("http")
async def redirect_to_canonical_collection_path(request, call_next):
    """Restore the trailing-slash redirect that the static mount would eat.

    Collection routes are declared as "/books/", and FastAPI normally answers
    "/books" with a 307 to it. Mounting StaticFiles at "/" breaks that: the
    mount matches any path, so "/books" reaches the file server and comes back
    as a bare 404 that reads as "no such endpoint". Redirecting here, before
    routing, keeps the mount at the root without making the API confusing.
    """
    if request.method in ("GET", "HEAD") and request.url.path in collection_paths():
        location = f"{request.url.path}/"
        if request.url.query:
            location = f"{location}?{request.url.query}"
        return RedirectResponse(location, status_code=307)
    return await call_next(request)


# Added after the redirect middleware so it wraps it: every response, including
# a redirect, gets timed and logged.
@app.middleware("http")
async def log_requests(request, call_next):
    """Time every request and give it a traceable id.

    An inbound X-Request-ID is honoured so a trace started by a proxy or the
    caller survives; otherwise one is minted here. Either way it goes back on
    the response and into every log record emitted while handling the request.
    """
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    request.state.request_id = request_id
    token = request_id_var.set(request_id)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Without this the failing path logs nothing and the id is lost.
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "duration_s": f"{time.perf_counter() - start:.4f}",
            },
        )
        raise
    finally:
        request_id_var.reset(token)

    duration = time.perf_counter() - start
    logger.info(
        "request handled",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_s": f"{duration:.4f}",
            "request_id": request_id,
        },
    )
    response.headers["request-process-time"] = f"{duration:.4f}"
    response.headers[REQUEST_ID_HEADER] = request_id
    return response

app.include_router(health_router.router)
app.include_router(user_router.router)
app.include_router(book_router.router)
app.include_router(weather_router.router)
app.include_router(auth_router.router)
app.include_router(borrowing_router.router)

# Mounted last and at the root, so it only handles paths no router claimed.
# html=True serves index.html for "/", which makes the frontend same-origin
# with the API: no CORS preflight, and no hardcoded 127.0.0.1 in app.js.
FRONTEND_DIR = Path(__file__).parent / "core" / "frontend"
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:  # pragma: no cover - only if the tree is checked out incompletely
    logger.warning("frontend directory missing, static files not served",
                   extra={"path": str(FRONTEND_DIR)})

# Run with: uv run uvicorn src.main:app --reload
