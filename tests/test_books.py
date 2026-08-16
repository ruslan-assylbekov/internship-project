from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.book_router import get_book_service
from src.main import app
from src.models.enums import BookStatus
from src.repositories.book_repository import BookRepository
from src.services.book_service import BookService


def make_book(book_id: int = 1, status: str = BookStatus.AVAILABLE.value):
    return {
        "id": book_id,
        "title": "Test-Title",
        "author": "Test-Author",
        "year": 2000,
        "status": status,
    }


def override_service(service):
    app.dependency_overrides[get_book_service] = lambda: service


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


def test_book_service_forwards_paging_and_filters():
    repository = MagicMock()
    service = BookService(repository)

    service.get_all_books(skip=10, limit=5, q="dosto", status="Available")

    repository.get_all.assert_called_once_with(
        skip=10, limit=5, q="dosto", status="Available"
    )


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
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["title"] == "Test-Title"
    service.get_book_by_id.assert_called_once_with(1)


def test_book_api_exposes_status_so_the_catalogue_reflects_borrowing():
    service = MagicMock()
    service.get_book_by_id.return_value = make_book(status=BookStatus.BORROWED.value)
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/1")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["status"] == "Borrowed"


def test_browsing_the_catalogue_needs_no_token():
    """Reading the catalogue is public; only changing it is not."""
    service = MagicMock()
    service.get_all_books.return_value = [make_book()]
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_book_list_forwards_search_filter_and_paging():
    service = MagicMock()
    service.get_all_books.return_value = []
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/?q=dosto&status=Available&skip=5&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    service.get_all_books.assert_called_once_with(
        skip=5, limit=10, q="dosto", status=BookStatus.AVAILABLE
    )


def test_book_list_defaults_are_applied_when_no_params_are_given():
    service = MagicMock()
    service.get_all_books.return_value = []
    override_service(service)

    try:
        with TestClient(app) as client:
            client.get("/books/")
    finally:
        app.dependency_overrides.clear()

    assert service.get_all_books.call_args.kwargs == {
        "skip": 0,
        "limit": 50,
        "q": None,
        "status": None,
    }


def test_book_list_rejects_an_unknown_status():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/?status=Wandering")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.get_all_books.assert_not_called()


def test_book_list_caps_the_page_size():
    """Without a cap, ?limit=100000 is a denial-of-service handed to callers."""
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/books/?limit=1000")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.get_all_books.assert_not_called()


def test_book_post_wrong_type_is_rejected_before_service_call(authenticated):
    service = MagicMock()
    override_service(service)

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


def test_book_api_create_returns_201(authenticated):
    service = MagicMock()
    service.create_book.return_value = make_book()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/books/",
                json={"title": "Test-Title", "author": "Test-Author", "year": 2000},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["title"] == "Test-Title"


def test_creating_a_book_requires_a_token():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/books/",
                json={"title": "Test-Title", "author": "Test-Author", "year": 2000},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    service.create_book.assert_not_called()


def test_deleting_a_book_requires_a_token():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete("/books/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    service.delete_book.assert_not_called()


def test_book_delete_returns_204_with_no_body(authenticated):
    """Every delete in this API answers the same way, so clients need no
    special case per resource.
    """
    service = MagicMock()
    service.delete_book.return_value = True
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete("/books/1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_book_delete_returns_404_for_a_missing_book(authenticated):
    service = MagicMock()
    service.delete_book.return_value = False
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.delete("/books/404")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


# --------------------------------------------------------------------------
# BookCreate validation: a junk row is cheaper to reject than to clean up.
# --------------------------------------------------------------------------

def post_book(authenticated_service, **overrides):
    payload = {"title": "Test-Title", "author": "Test-Author", "year": 2000}
    payload.update(overrides)
    override_service(authenticated_service)

    try:
        with TestClient(app) as client:
            return client.post("/books/", json=payload)
    finally:
        app.dependency_overrides.clear()


def test_empty_title_is_rejected(authenticated):
    service = MagicMock()

    response = post_book(service, title="")

    assert response.status_code == 422
    service.create_book.assert_not_called()


def test_whitespace_only_title_is_rejected(authenticated):
    """Stripped before the length check, so "   " cannot slip past min_length."""
    service = MagicMock()

    response = post_book(service, title="   ")

    assert response.status_code == 422
    service.create_book.assert_not_called()


def test_surrounding_whitespace_is_stripped_before_storing(authenticated):
    service = MagicMock()
    service.create_book.return_value = make_book()

    post_book(service, title="  The Brothers Karamazov  ")

    assert service.create_book.call_args.args[0]["title"] == "The Brothers Karamazov"


def test_overlong_title_is_rejected(authenticated):
    service = MagicMock()

    response = post_book(service, title="x" * 5000)

    assert response.status_code == 422
    service.create_book.assert_not_called()


def test_empty_author_is_rejected(authenticated):
    service = MagicMock()

    response = post_book(service, author="")

    assert response.status_code == 422


def test_negative_year_is_rejected(authenticated):
    service = MagicMock()

    response = post_book(service, year=-500)

    assert response.status_code == 422
    service.create_book.assert_not_called()


def test_implausibly_future_year_is_rejected(authenticated):
    service = MagicMock()

    response = post_book(service, year=9999)

    assert response.status_code == 422
    service.create_book.assert_not_called()


def test_next_year_is_accepted_for_books_catalogued_early(authenticated):
    from datetime import UTC, datetime

    service = MagicMock()
    service.create_book.return_value = make_book()

    response = post_book(service, year=datetime.now(UTC).year + 1)

    assert response.status_code == 201
