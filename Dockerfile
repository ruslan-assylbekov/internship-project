# syntax=docker/dockerfile:1

# Matches .python-version and requires-python in pyproject.toml.
FROM python:3.14-slim

# uv drives dependency installation, as it does locally; the previous image
# installed from requirements.txt, which is no longer maintained.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

# Install dependencies first, from the lockfile only, so that editing source
# does not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . .

EXPOSE 8000

# The module path is src.main:app -- the old core.backend.main:app stopped
# existing when the code moved under src/.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
