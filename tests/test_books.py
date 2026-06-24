from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from core.backend.main import app
from src.api.book_router import get_book_service
from src.repositories.book_repository import BookRepository
from src.services.book_service import BookService


def make_book(book_id: int = 1):
    return {
        "id": book_id,
        "title": "Test-Title",
        "author": "Test-Author",
        "year": 2000,
    }


def test_book_service_gets_book_from_repository():
    repository = MagicMock()
    repository.get_by_id.return_value = make_book()
    service = BookService(repository)

    result = service.get_book_by_id(1)

    repository.get_by_id.assert_called_once_with(1)
    assert result["title"] == "Test-Title"


def test_book_service_creates_book_through_repository():
    repository = MagicMock()
    book_data = {"title": "Test-Title", "author": "Test-Author", "year": 2000}
    repository.create.return_value = make_book()
    service = BookService(repository)

    result = service.create_book(book_data)

    repository.create.assert_called_once_with(book_data)
    assert result["year"] == 2000


def test_book_repository_create_uses_session_without_real_database():
    db = MagicMock()
    repo = BookRepository(db)
    book_data = {"title": "Test-Title", "author": "Test-Author", "year": 2000}

    result = repo.create(book_data)

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)
    assert result.title == "Test-Title"


def test_book_api_get_by_id_uses_mocked_service():
    service = MagicMock()
    service.get_book_by_id.return_value = make_book()
    app.dependency_overrides[get_book_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/books/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["title"] == "Test-Title"
    service.get_book_by_id.assert_called_once_with(1)


def test_book_post_wrong_type_is_rejected_before_service_call():
    service = MagicMock()
    app.dependency_overrides[get_book_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/books/",
                json={"title": "Test-Title", "author": "Test-Author", "year": "old"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.create_book.assert_not_called()
