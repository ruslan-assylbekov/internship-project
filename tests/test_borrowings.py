"""Borrowing rules and their HTTP mapping.

Split deliberately: the service tests assert the rules against mock
repositories, the API tests assert only that each domain error becomes the
right status code. The same rules are also exercised against a real engine in
test_integration.py -- mocks cannot catch a broken query.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.borrowing_router import get_borrowing_service
from src.main import app
from src.models.database_models import LOAN_PERIOD_DAYS, utcnow
from src.models.enums import BookStatus, BorrowingStatus
from src.services.borrowing_service import (
    BookNotFound,
    BookUnavailable,
    BorrowingAlreadyClosed,
    BorrowingNotFound,
    BorrowingService,
    NotTheBorrower,
)


def make_book(book_id: int = 7, status: str = BookStatus.AVAILABLE.value):
    return SimpleNamespace(id=book_id, status=status)


def make_borrowing_row(
    borrowing_id: int = 1,
    user_id: int = 1,
    status: str = BorrowingStatus.ACTIVE.value,
):
    return SimpleNamespace(
        id=borrowing_id,
        user_id=user_id,
        book_id=7,
        status=status,
        return_date=None,
        book=make_book(status=BookStatus.BORROWED.value),
    )


def make_service(book=None, open_row=None):
    borrowing_repository = MagicMock()
    book_repository = MagicMock()
    book_repository.get_by_id.return_value = book
    borrowing_repository.get_open_for_book.return_value = open_row
    return BorrowingService(borrowing_repository, book_repository), borrowing_repository


# --------------------------------------------------------------------------
# Borrowing
# --------------------------------------------------------------------------

def test_borrow_opens_a_loan_and_marks_the_book_borrowed():
    """The book's status is what the catalogue shows, so it moves with the loan."""
    service, repository = make_service(book=make_book())

    service.borrow(user_id=3, book_id=7)

    kwargs = repository.open.call_args.kwargs
    assert repository.open.call_args.args[0].id == 7
    assert kwargs["user_id"] == 3
    assert kwargs["status"] is BorrowingStatus.ACTIVE
    assert kwargs["book_status"] == BookStatus.BORROWED.value


def test_borrow_sets_a_due_date_one_loan_period_out():
    service, repository = make_service(book=make_book())

    service.borrow(user_id=3, book_id=7)

    expected = utcnow() + timedelta(days=LOAN_PERIOD_DAYS)
    actual = repository.open.call_args.kwargs["due_date"]
    assert abs((actual - expected).total_seconds()) < 5


def test_borrowing_an_unknown_book_is_not_found():
    service, repository = make_service(book=None)

    with pytest.raises(BookNotFound):
        service.borrow(user_id=3, book_id=404)

    repository.open.assert_not_called()


def test_borrowing_an_already_borrowed_book_is_a_conflict():
    """The core rule of a library: one copy, one borrower."""
    service, repository = make_service(book=make_book(status=BookStatus.BORROWED.value))

    with pytest.raises(BookUnavailable):
        service.borrow(user_id=3, book_id=7)

    repository.open.assert_not_called()


def test_borrowing_a_lost_book_is_a_conflict():
    service, _ = make_service(book=make_book(status=BookStatus.LOST.value))

    with pytest.raises(BookUnavailable):
        service.borrow(user_id=3, book_id=7)


def test_an_open_row_blocks_a_borrow_even_if_the_column_says_available():
    """Belt and braces: the column can be stale, the open row is authoritative."""
    service, repository = make_service(
        book=make_book(status=BookStatus.AVAILABLE.value),
        open_row=make_borrowing_row(),
    )

    with pytest.raises(BookUnavailable):
        service.borrow(user_id=3, book_id=7)

    repository.open.assert_not_called()


# --------------------------------------------------------------------------
# Reserving
# --------------------------------------------------------------------------

def test_reserve_marks_the_book_reserved_without_a_due_date():
    """A hold is not a loan, so nothing is due back yet."""
    service, repository = make_service(book=make_book())

    service.reserve(user_id=3, book_id=7)

    kwargs = repository.open.call_args.kwargs
    assert kwargs["status"] is BorrowingStatus.RESERVED
    assert kwargs["book_status"] == BookStatus.RESERVED.value
    assert kwargs.get("due_date") is None


def test_reserving_an_unavailable_book_is_a_conflict():
    service, _ = make_service(book=make_book(status=BookStatus.RESERVED.value))

    with pytest.raises(BookUnavailable):
        service.reserve(user_id=3, book_id=7)


# --------------------------------------------------------------------------
# Returning and writing off
# --------------------------------------------------------------------------

def test_return_closes_the_loan_and_frees_the_book():
    borrowing = make_borrowing_row(user_id=3)
    service, repository = make_service()
    repository.get_by_id.return_value = borrowing

    service.return_book(user_id=3, borrowing_id=1)

    kwargs = repository.close.call_args.kwargs
    assert kwargs["status"] is BorrowingStatus.RETURNED
    assert kwargs["book_status"] == BookStatus.AVAILABLE.value
    assert kwargs["return_date"] is not None


def test_a_reservation_can_be_cancelled_by_returning_it():
    borrowing = make_borrowing_row(user_id=3, status=BorrowingStatus.RESERVED.value)
    service, repository = make_service()
    repository.get_by_id.return_value = borrowing

    service.return_book(user_id=3, borrowing_id=1)

    assert repository.close.call_args.kwargs["book_status"] == BookStatus.AVAILABLE.value


def test_report_lost_writes_the_book_off_without_a_return_date():
    """A lost book never came back, so recording a return date would be a lie."""
    borrowing = make_borrowing_row(user_id=3)
    service, repository = make_service()
    repository.get_by_id.return_value = borrowing

    service.report_lost(user_id=3, borrowing_id=1)

    kwargs = repository.close.call_args.kwargs
    assert kwargs["status"] is BorrowingStatus.LOST
    assert kwargs["book_status"] == BookStatus.LOST.value
    assert kwargs.get("return_date") is None


def test_returning_an_unknown_borrowing_is_not_found():
    service, repository = make_service()
    repository.get_by_id.return_value = None

    with pytest.raises(BorrowingNotFound):
        service.return_book(user_id=3, borrowing_id=404)

    repository.close.assert_not_called()


def test_returning_someone_elses_borrowing_is_forbidden():
    service, repository = make_service()
    repository.get_by_id.return_value = make_borrowing_row(user_id=99)

    with pytest.raises(NotTheBorrower):
        service.return_book(user_id=3, borrowing_id=1)

    repository.close.assert_not_called()


def test_returning_twice_is_a_conflict():
    service, repository = make_service()
    repository.get_by_id.return_value = make_borrowing_row(
        user_id=3, status=BorrowingStatus.RETURNED.value
    )

    with pytest.raises(BorrowingAlreadyClosed):
        service.return_book(user_id=3, borrowing_id=1)

    repository.close.assert_not_called()


def test_a_lost_book_cannot_be_returned():
    service, repository = make_service()
    repository.get_by_id.return_value = make_borrowing_row(
        user_id=3, status=BorrowingStatus.LOST.value
    )

    with pytest.raises(BorrowingAlreadyClosed):
        service.return_book(user_id=3, borrowing_id=1)


def test_ownership_is_checked_before_state():
    """Otherwise the error tells a stranger whether the borrowing is still open."""
    service, repository = make_service()
    repository.get_by_id.return_value = make_borrowing_row(
        user_id=99, status=BorrowingStatus.RETURNED.value
    )

    with pytest.raises(NotTheBorrower):
        service.return_book(user_id=3, borrowing_id=1)


def test_listing_forwards_paging():
    service, repository = make_service()

    service.get_borrowings_for_user(3, skip=10, limit=5)

    repository.get_by_user.assert_called_once_with(3, skip=10, limit=5)


# --------------------------------------------------------------------------
# API: the router's only job is turning domain errors into status codes.
# --------------------------------------------------------------------------

def make_borrowing_payload(borrowing_id: int = 1, status: str = "Active"):
    return {
        "id": borrowing_id,
        "book_id": 7,
        "user_id": 1,
        "status": status,
        "borrow_date": datetime.now(UTC).isoformat(),
        "due_date": (datetime.now(UTC) + timedelta(days=14)).isoformat(),
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
    app.dependency_overrides[get_borrowing_service] = lambda: service


def test_borrow_endpoint_returns_201(authenticated):
    service = MagicMock()
    service.borrow.return_value = make_borrowing_payload()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/borrow", json={"book_id": 7})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["book"]["title"] == "Test-Title"


def test_the_borrower_comes_from_the_token_not_the_body(authenticated):
    """Otherwise a caller could borrow on someone else's behalf."""
    service = MagicMock()
    service.borrow.return_value = make_borrowing_payload()
    override_service(service)

    try:
        with TestClient(app) as client:
            client.post("/borrowings/borrow", json={"book_id": 7, "user_id": 999})
    finally:
        app.dependency_overrides.clear()

    service.borrow.assert_called_once_with(authenticated.id, 7)


def test_every_borrowing_endpoint_requires_a_token():
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            responses = [
                client.get("/borrowings/"),
                client.get("/borrowings/me"),
                client.post("/borrowings/borrow", json={"book_id": 7}),
                client.post("/borrowings/reserve", json={"book_id": 7}),
                client.post("/borrowings/1/return"),
                client.post("/borrowings/1/report-lost"),
            ]
    finally:
        app.dependency_overrides.clear()

    assert [r.status_code for r in responses] == [401] * 6
    service.borrow.assert_not_called()


def test_unknown_book_becomes_404(authenticated):
    service = MagicMock()
    service.borrow.side_effect = BookNotFound("book 404 does not exist")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/borrow", json={"book_id": 404})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "book 404 does not exist"


def test_unavailable_book_becomes_409(authenticated):
    service = MagicMock()
    service.borrow.side_effect = BookUnavailable("book 7 is Borrowed")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/borrow", json={"book_id": 7})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_someone_elses_borrowing_becomes_403(authenticated):
    service = MagicMock()
    service.return_book.side_effect = NotTheBorrower("that borrowing belongs to another user")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/1/return")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_closed_borrowing_becomes_409(authenticated):
    service = MagicMock()
    service.return_book.side_effect = BorrowingAlreadyClosed("borrowing 1 is Returned")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/1/return")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_missing_borrowing_becomes_404(authenticated):
    service = MagicMock()
    service.report_lost.side_effect = BorrowingNotFound("borrowing 404 does not exist")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/404/report-lost")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_my_borrowings_only_asks_for_the_callers_rows(authenticated):
    service = MagicMock()
    service.get_borrowings_for_user.return_value = [make_borrowing_payload()]
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.get("/borrowings/me?skip=5&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    service.get_borrowings_for_user.assert_called_once_with(
        authenticated.id, skip=5, limit=10
    )


def test_reserve_endpoint_returns_201(authenticated):
    service = MagicMock()
    service.reserve.return_value = make_borrowing_payload(status="Reserved")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/reserve", json={"book_id": 7})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "Reserved"


def test_return_endpoint_returns_200(authenticated):
    service = MagicMock()
    service.return_book.return_value = make_borrowing_payload(status="Returned")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/1/return")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    service.return_book.assert_called_once_with(authenticated.id, 1)


def test_report_lost_endpoint_returns_200(authenticated):
    service = MagicMock()
    service.report_lost.return_value = make_borrowing_payload(status="Lost")
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/1/report-lost")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "Lost"


def test_a_missing_book_id_is_rejected_before_the_service(authenticated):
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/borrow", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.borrow.assert_not_called()


def test_a_non_positive_book_id_is_rejected(authenticated):
    service = MagicMock()
    override_service(service)

    try:
        with TestClient(app) as client:
            response = client.post("/borrowings/borrow", json={"book_id": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    service.borrow.assert_not_called()
