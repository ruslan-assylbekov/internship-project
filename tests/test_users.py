from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.user_router import get_user_service
from src.core.security import hash_password
from src.main import app
from src.repositories.user_repository import UserRepository
from src.services.user_service import UserService


def make_user(user_id: int = 1):
    return {
        "id": user_id,
        "email": "ruslan@example.com",
        "firstname": "Ruslan",
        "lastname": "Assylbekov",
        "created": datetime.now(UTC).isoformat(),
    }


def make_borrowing(borrowing_id: int = 1):
    return {
        "id": borrowing_id,
        "book_id": 7,
        "user_id": 1,
        "status": "Active",
        "borrow_date": datetime.now(UTC).isoformat(),
        "due_date": datetime.now(UTC).isoformat(),
        "return_date": None,
        "book": {
            "id": 7,
            "title": "Test-Title",
            "author": "Test-Author",
            "year": 2000,
            "status": "Borrowed",
        },
    }


def override_service(service):
    app.dependency_overrides[get_user_service] = lambda: service


def test_user_service_gets_user_from_repository():
    repository = MagicMock()
    repository.get_by_id.return_value = make_user()
    service = UserService(repository)

    result = service.get_user_by_id(1)

    repository.get_by_id.assert_called_once_with(1)
    assert result["firstname"] == "Ruslan"


def test_user_service_hashes_password_before_storing():
    repository = MagicMock()
    user_data = {
        "email": "ruslan@example.com",
        "password": "correct horse battery",
        "firstname": "Ruslan",
        "lastname": "Assylbekov",
    }
    repository.create.return_value = make_user()
    service = UserService(repository)

    result = service.create_user(user_data)

    stored = repository.create.call_args.args[0]
    assert stored["password"] != "correct horse battery"
    assert stored["password"].startswith("$2b$")
    # The caller's dict must not be mutated.
    assert user_data["password"] == "correct horse battery"
    assert result["email"] == "ruslan@example.com"


def test_user_service_forwards_paging():
    repository = MagicMock()
    service = UserService(repository)

    service.get_all_users(skip=20, limit=10)

    repository.get_all.assert_called_once_with(skip=20, limit=10)


def test_user_repository_create_uses_session_without_real_database():
    db = MagicMock()
    repo = UserRepository(db)
    user_data = {
        "email": "ruslan@example.com",
        "password": "pass",
        "firstname": "Ruslan",
        "lastname": "Assylbekov",
    }

    result = repo.create(user_data)

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)
    assert result.firstname == "Ruslan"


def test_user_api_get_by_id_uses_mocked_service():
    service = MagicMock()
    service.get_user_by_id.return_value = make_user()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["firstname"] == "Ruslan"
    service.get_user_by_id.assert_called_once_with(1)


def test_user_detail_lists_what_the_user_borrowed():
    """Viewing a user used to give no way to see their loans."""
    service = MagicMock()
    service.get_user_by_id.return_value = make_user() | {"borrowings": [make_borrowing()]}
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/1")
    finally:
        app.dependency_overrides.clear()

    borrowings = response.json()["borrowings"]
    assert len(borrowings) == 1
    assert borrowings[0]["book"]["title"] == "Test-Title"


def test_user_detail_defaults_borrowings_to_empty():
    service = MagicMock()
    service.get_user_by_id.return_value = make_user()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/1")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["borrowings"] == []


def test_user_api_returns_404_when_service_has_no_user():
    service = MagicMock()
    service.get_user_by_id.return_value = None
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/404")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_user_list_forwards_paging():
    service = MagicMock()
    service.get_all_users.return_value = []
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/?skip=30&limit=15")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    service.get_all_users.assert_called_once_with(skip=30, limit=15)


def test_user_list_rejects_a_negative_skip():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/users/?skip=-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.get_all_users.assert_not_called()


def test_users_me_returns_the_token_holder(authenticated):
    """The route must be declared before /{user_id}, or "me" is parsed as an id."""
    with TestClient(app) as client:
        response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["id"] == authenticated.id
    assert response.json()["email"] == "ruslan@example.com"


def test_users_me_requires_a_token():
    with TestClient(app) as client:
        response = client.get("/users/me")

    assert response.status_code == 401


def test_user_api_create_returns_201():
    service = MagicMock()
    service.get_user_by_email.return_value = None
    service.create_user.return_value = make_user()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/",
                json={
                    "email": "ruslan@example.com",
                    "password": "long-enough-password",
                    "firstname": "Ruslan",
                    "lastname": "Assylbekov",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["email"] == "ruslan@example.com"


def test_registering_needs_no_token():
    """Signup cannot require the credential it exists to create."""
    service = MagicMock()
    service.get_user_by_email.return_value = None
    service.create_user.return_value = make_user()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/",
                json={
                    "email": "new@example.com",
                    "password": "long-enough-password",
                    "firstname": "New",
                    "lastname": "Person",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201


def test_user_api_rejects_duplicate_email():
    service = MagicMock()
    service.get_user_by_email.return_value = make_user()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/",
                json={
                    "email": "ruslan@example.com",
                    "password": "long-enough-password",
                    "firstname": "Ruslan",
                    "lastname": "Assylbekov",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    service.create_user.assert_not_called()


def test_user_api_rejects_short_password_before_service_call():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/",
                json={
                    "email": "ruslan@example.com",
                    "password": "short",
                    "firstname": "Ruslan",
                    "lastname": "Assylbekov",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.create_user.assert_not_called()


def test_user_api_rejects_an_empty_name():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/users/",
                json={
                    "email": "ruslan@example.com",
                    "password": "long-enough-password",
                    "firstname": "",
                    "lastname": "Assylbekov",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_deleting_a_user_requires_a_token():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete("/users/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    service.delete_user.assert_not_called()


def test_user_delete_returns_204_with_no_body(authenticated):
    service = MagicMock()
    service.delete_user.return_value = True
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete(f"/users/{authenticated.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_a_user_cannot_delete_someone_else(authenticated):
    """There is no role model yet, so a token authorises its own account only."""
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete("/users/999")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    service.delete_user.assert_not_called()


def test_authenticate_accepts_matching_password():
    repository = MagicMock()
    stored = MagicMock()
    stored.password = hash_password("correct horse battery")
    repository.get_by_email.return_value = stored
    service = UserService(repository)

    assert service.authenticate("ruslan@example.com", "correct horse battery") is stored


def test_authenticate_rejects_wrong_password():
    repository = MagicMock()
    stored = MagicMock()
    stored.password = hash_password("correct horse battery")
    repository.get_by_email.return_value = stored
    service = UserService(repository)

    assert service.authenticate("ruslan@example.com", "wrong") is None


def test_authenticate_rejects_unknown_email():
    repository = MagicMock()
    repository.get_by_email.return_value = None
    service = UserService(repository)

    assert service.authenticate("nobody@example.com", "whatever") is None


def test_authenticate_rejects_legacy_plaintext_row():
    """Rows written before hashing hold plaintext; they must fail closed."""
    repository = MagicMock()
    stored = SimpleNamespace(password="plaintext-from-before-hashing")
    repository.get_by_email.return_value = stored
    service = UserService(repository)

    assert service.authenticate("old@example.com", "plaintext-from-before-hashing") is None
