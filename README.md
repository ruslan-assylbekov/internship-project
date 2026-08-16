# internship-project

FastAPI service for a small library app: users, books, borrowings, and a weather
lookup. PostgreSQL via SQLAlchemy, schema managed by Alembic, JWT bearer auth,
plus a static HTML/JS dashboard served by the app itself.

## Setup

```bash
uv sync
cp .env.example .env    # then fill in API_KEY from weatherapi.com, and SECRET_KEY
```

`SECRET_KEY` signs access tokens. Leaving it unset works, but the app generates
an ephemeral key per process, so every restart invalidates outstanding tokens.
`.env.example` documents every variable and how to generate a key.

## Running

```bash
uv run alembic upgrade head              # create/update tables
uv run uvicorn src.main:app --reload     # http://127.0.0.1:8000 (docs at /docs)
```

Or the whole stack, including Postgres and the migration step:

```bash
docker compose up --build
```

The frontend is mounted at the root by the app, so `http://127.0.0.1:8000/`
serves the dashboard and the API is same-origin — no need to open the HTML file
from disk.

## Tests

```bash
uv run pytest                            # all
uv run pytest tests/test_auth.py         # one file
uv run pytest tests/test_integration.py  # integration layer only
uv run pytest -k weather                 # by name
```

No database or network access is required. Most tests mock their collaborators;
`tests/test_integration.py` runs the repositories, services and the full API
against an in-memory SQLite engine instead, which is what catches broken
queries, missing cascades and constraint problems that mocks cannot. Postgres
is still the only target for the Alembic migrations, so that file does not
exercise them.

## Lint and format

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
```

Ruff config lives in `pyproject.toml`. `.pre-commit-config.yaml` runs the same
checks on commit — `uvx pre-commit install` to enable it (via `uvx` because
pre-commit is a developer tool, not a dependency of the app). `.github/workflows/ci.yml`
runs lint plus the test suite on every push and pull request. The formatter is
still being adopted, so its CI step is advisory rather than blocking.

## Project structure

A strict four-layer dependency flow, one layer per directory under `src/`. Each
layer only ever calls the one below it:

```
api/ (routers, HTTP only)
  -> services/ (business rules)
    -> repositories/ (the only layer holding a Session)
      -> models/ (SQLAlchemy tables)
```

`core/` and `schemas/` sit alongside rather than inside that chain.

```
src/
  main.py                       app, CORS, request logging middleware, router
                                registration, frontend mount
  api/                          routers: HTTP concerns only
    dependencies.py             the single wiring point for services and
                                get_current_user
    pagination.py               shared skip/limit dependency
    health_router.py            GET /health
    auth_router.py              login, token, me
    user_router.py
    book_router.py
    borrowing_router.py
    weather_router.py
  services/                     business rules; take plain dicts, never Pydantic
    user_service.py             hashes on create, owns authenticate
    book_service.py
    borrowing_service.py        the borrow/reserve/return/lost lifecycle
    weather_service.py          calls weatherapi.com; no database layer
  repositories/                 each takes db: Session and commits its own writes
    user_repository.py
    book_repository.py
    borrowing_repository.py
  models/
    database_models.py          all SQLAlchemy models
    enums.py                    BookStatus / BorrowingStatus
  schemas/                      Pydantic request and response models
    user_schemas.py
    book_schemas.py
    borrowing_schemas.py
    login_schemas.py
    weather_schemas.py
  core/
    config.py                   Settings, resolved lazily via get_settings()
    security.py                 bcrypt hashing, JWT sign and decode
    logging_config.py           key=value formatter, request-id context
    database/database_connect.py  engine and get_session
    frontend/                   static dashboard, mounted at /
alembic/versions/               migrations; schema is owned entirely by Alembic
tests/
```

## Authentication

`POST /auth/login` takes JSON and returns `{access_token, token_type, user}`.
`POST /auth/token` is the OAuth2 password-grant form equivalent, and exists so
the **Authorize** button in `/docs` works — it carries the email in the
spec-mandated `username` field.

Send the token as `Authorization: Bearer <token>` on protected endpoints. A
token resolves to a user row on every request, so deleting an account takes
effect immediately rather than at token expiry.

## Endpoints

The **Auth** column marks endpoints that require a bearer token.

| Method | Path                            | Auth  | Notes                                          |
| ------ | ------------------------------- | ----- | ---------------------------------------------- |
| GET    | `/health`                       |       | 200 ok / 503 degraded, per database reachability |
| POST   | `/auth/login`                   |       | JSON; returns token + user; 401 on bad credentials |
| POST   | `/auth/token`                   |       | OAuth2 form grant, for the /docs Authorize button |
| GET    | `/auth/me`                      | yes   | the caller's profile, with their borrowings    |
| GET    | `/users/`                       |       | list users; `skip`/`limit`                     |
| GET    | `/users/me`                     | yes   | same as `/auth/me`                             |
| GET    | `/users/{id}`                   |       | 404 when absent                                |
| POST   | `/users/`                       |       | 201; 409 on duplicate email                    |
| DELETE | `/users/{id}`                   | yes   | 204; own account only (403 otherwise)          |
| GET    | `/books/`                       |       | `skip`/`limit`, `q` (title or author), `status` |
| GET    | `/books/{id}`                   |       | 404 when absent                                |
| POST   | `/books/`                       | yes   | 201                                            |
| DELETE | `/books/{id}`                   | yes   | 204; 404 when absent                           |
| GET    | `/borrowings/`                  | yes   | every borrowing; `skip`/`limit`                |
| GET    | `/borrowings/me`                | yes   | the caller's borrowings                        |
| POST   | `/borrowings/borrow`            | yes   | 201; 404 unknown book, 409 unavailable         |
| POST   | `/borrowings/reserve`           | yes   | 201; a hold, so no due date                    |
| POST   | `/borrowings/{id}/return`       | yes   | 403 if not yours, 409 if already closed        |
| POST   | `/borrowings/{id}/report-lost`  | yes   | writes the book off instead of reshelving it   |
| GET    | `/weather/{city}`               |       | current conditions; 502 if provider fails      |

List endpoints take `skip` (default 0) and `limit` (default 50, max 100).
Deletes return `204 No Content`.

The borrower is always taken from the token, never from the request body, so
nobody can borrow on someone else's behalf.

## Book status

A book is `Available`, `Borrowed`, `Reserved`, or `Lost`. The status is not set
directly — it is maintained by the borrowing lifecycle:

| Action        | Borrowing becomes | Book becomes |
| ------------- | ----------------- | ------------ |
| borrow        | `Active`          | `Borrowed`   |
| reserve       | `Reserved`        | `Reserved`   |
| return        | `Returned`        | `Available`  |
| report lost   | `Lost`            | `Lost`       |

Borrowing a book requires it to be `Available` and to have no open borrowing
row; a loan is due back 14 days later, while a reservation has no due date.

## Migrations

```bash
uv run alembic upgrade head                              # apply
uv run alembic revision --autogenerate -m "message"      # new revision
```

The current head is `b7c41d9e2f38`, which adds `borrowings.status` and
`borrowings.due_date` and backfills both for rows written before it.

## Known gaps

- **No roles.** Every authenticated user is equivalent, so the only ownership
  rule that can be enforced is "your own row": deleting a user is restricted to
  self-service, and any token may add or remove books.
- Accounts created before password hashing was introduced hold plaintext and
  can no longer log in; they need a password reset.
- Timestamps are stored naive. Moving to `DateTime(timezone=True)` needs a
  migration that reinterprets existing rows against the server timezone.
- The Docker image has not been built or run — no daemon was available to
  verify it.
