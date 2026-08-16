"""Fixtures shared by every test file.

``src.main.app`` is created once at import and shared by the whole suite, so a
dependency override that outlives its test silently changes another file's
results. Tests still clear their own overrides in a ``finally``; the autouse
fixture below is the backstop for the ones that raise before getting there.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from src.api.dependencies import get_current_user
from src.main import app


@pytest.fixture(autouse=True)
def restore_dependency_overrides():
    """Undo whatever a test added, keep whatever it inherited.

    Restoring a snapshot rather than clearing outright, so a module- or
    session-scoped override set up by a fixture survives the tests that run
    underneath it.
    """
    original = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)


@pytest.fixture
def current_user():
    """A stand-in for the row ``get_current_user`` resolves a token to.

    An object rather than a dict: routers read ``current_user.id`` to decide
    ownership, which a dict would not support.
    """
    return SimpleNamespace(
        id=1,
        email="ruslan@example.com",
        firstname="Ruslan",
        lastname="Assylbekov",
        created=datetime.now(UTC),
        borrowings=[],
    )


@pytest.fixture
def authenticated(current_user):
    """Bypass token verification for tests about something else."""
    app.dependency_overrides[get_current_user] = lambda: current_user
    return current_user
