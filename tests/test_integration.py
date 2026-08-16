"""Integration tests: no mocks, a real SQLAlchemy engine.

The rest of the suite mocks its collaborators, which is fast but structurally
blind -- a mock repository cannot have a broken query, a mock Session cannot
violate a foreign key, and a MagicMock relationship cannot fail to cascade.
These tests run the repositories, the services and the whole API against a
live engine so that class of bug has somewhere to surface.

SQLite in memory rather than Testcontainers, because the suite must keep
running with no Docker and no network. What that trades away:

* ``ilike`` compiles to ``lower(x) LIKE lower(y)`` here, so Postgres' own
  case-folding rules are not exercised.
* Postgres-only SQL (the ``INTERVAL`` backfill in revision b7c41d9e2f38) never
  runs -- the schema comes from ``Base.metadata.create_all``, so the Alembic
  migrations remain unverified by this file and Postgres-only by design.
* Foreign keys are off unless asked for, hence the PRAGMA below.
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database.database_connect import get_session
from src.main import app
from src.models.database_models import (
    LOAN_PERIOD_DAYS,
    Base,
    books,
    borrowings,
    users,
    utcnow,
)
from src.models.enums import BookStatus, BorrowingStatus
from src.repositories.book_repository import BookRepository
from src.repositories.borrowing_repository import BorrowingRepository
from src.repositories.user_repository import UserRepository
from src.services.borrowing_service import (
    BookNotFound,
    BookUnavailable,
    BorrowingAlreadyClosed,
    BorrowingService,
    NotTheBorrower,
)


@pytest.fixture
def engine():
    """A fresh database per test, so rows cannot leak between them.

    StaticPool plus one shared connection is required: every other pool hands
    each Session its own connection, and with ``sqlite://`` that means its own
    empty database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        # Off by default in SQLite, which would make the cascade tests below
        # pass for the wrong reason.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session(engine):
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(session):
    """The API driven against the real session, overriding the session rather
    than the services, so repositories and queries are part of the test.
    """
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def add_user(session, email="reader@example.com", firstname="Test"):
    user = users(
        email=email,
        password="not-a-real-hash",
        firstname=firstname,
        lastname="Reader",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def add_book(session, title="Test-Title", author="Test-Author", year=2000, status=None):
    book = books(
        title=title,
        author=author,
        year=year,
        status=(status or BookStatus.AVAILABLE.value),
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def add_borrowing(session, book, user, status=BorrowingStatus.ACTIVE.value):
    borrowing = borrowings(
        book_id=book.id, user_id=user.id, status=status, borrow_date=utcnow()
    )
    session.add(borrowing)
    session.commit()
    session.refresh(borrowing)
    return borrowing


# --------------------------------------------------------------------------
# UserRepository
# --------------------------------------------------------------------------

def test_user_round_trips_through_a_real_database(session):
    repository = UserRepository(session)

    created = repository.create(
        {
            "email": "ruslan@example.com",
            "password": "hashed",
            "firstname": "Ruslan",
            "lastname": "Assylbekov",
        }
    )

    assert repository.get_by_id(created.id).email == "ruslan@example.com"
    assert repository.get_by_email("ruslan@example.com").id == created.id
    # The column default has to be applied by the database, not the test.
    assert created.created is not None


def test_unknown_email_and_id_return_none(session):
    repository = UserRepository(session)

    assert repository.get_by_email("nobody@example.com") is None
    assert repository.get_by_id(404) is None


def test_user_pages_do_not_overlap(session):
    """The explicit order_by exists for this: without it SQL may return rows in
    any order, and two pages can then contain the same row.
    """
    repository = UserRepository(session)
    for index in range(5):
        add_user(session, email=f"reader{index}@example.com")

    first = repository.get_all(skip=0, limit=2)
    second = repository.get_all(skip=2, limit=2)

    assert len(first) == 2 and len(second) == 2
    assert {user.id for user in first}.isdisjoint({user.id for user in second})
    assert [user.id for user in first] == sorted(user.id for user in first)


def test_deleting_a_user_twice_reports_the_second_as_missing(session):
    repository = UserRepository(session)
    user = add_user(session)

    assert repository.delete(user.id) is True
    assert repository.delete(user.id) is False
    assert repository.get_by_id(user.id) is None


# --------------------------------------------------------------------------
# BookRepository: filtering is the part mocks cannot check at all.
# --------------------------------------------------------------------------

def test_search_matches_title_or_author_case_insensitively(session):
    repository = BookRepository(session)
    add_book(session, title="The Brothers Karamazov", author="Fyodor Dostoevsky")
    add_book(session, title="Anna Karenina", author="Leo Tolstoy")

    by_title = repository.get_all(q="brothers")
    by_author = repository.get_all(q="TOLSTOY")

    assert [book.title for book in by_title] == ["The Brothers Karamazov"]
    assert [book.title for book in by_author] == ["Anna Karenina"]


def test_search_finds_nothing_for_an_unmatched_term(session):
    repository = BookRepository(session)
    add_book(session)

    assert repository.get_all(q="no-such-book") == []


def test_a_percent_in_the_search_term_is_a_literal_not_a_wildcard(session):
    """Unescaped, "%" would turn any search into match-everything, and a user
    searching for "100%" would get the whole catalogue instead of one book.
    """
    repository = BookRepository(session)
    add_book(session, title="100% Cotton", author="Anon")
    add_book(session, title="Plain Title", author="Anon")

    assert [book.title for book in repository.get_all(q="100%")] == ["100% Cotton"]
    # Matches only titles/authors actually containing a percent sign.
    assert [book.title for book in repository.get_all(q="%")] == ["100% Cotton"]


def test_an_underscore_in_the_search_term_is_a_literal(session):
    """"_" is LIKE's single-character wildcard, so "a_c" would match "abc"."""
    repository = BookRepository(session)
    add_book(session, title="snake_case", author="Anon")
    add_book(session, title="snakeXcase", author="Anon")

    assert [book.title for book in repository.get_all(q="snake_case")] == ["snake_case"]


def test_books_can_be_filtered_by_status(session):
    repository = BookRepository(session)
    add_book(session, title="On The Shelf")
    add_book(session, title="Out On Loan", status=BookStatus.BORROWED.value)

    available = repository.get_all(status=BookStatus.AVAILABLE.value)

    assert [book.title for book in available] == ["On The Shelf"]


def test_search_and_status_filters_combine(session):
    repository = BookRepository(session)
    add_book(session, title="Karamazov Available")
    add_book(session, title="Karamazov Borrowed", status=BookStatus.BORROWED.value)

    result = repository.get_all(q="karamazov", status=BookStatus.BORROWED.value)

    assert [book.title for book in result] == ["Karamazov Borrowed"]


def test_book_pages_do_not_overlap(session):
    repository = BookRepository(session)
    for index in range(5):
        add_book(session, title=f"Book {index}")

    first = repository.get_all(skip=0, limit=2)
    second = repository.get_all(skip=2, limit=2)

    assert {book.id for book in first}.isdisjoint({book.id for book in second})


# --------------------------------------------------------------------------
# BorrowingRepository
# --------------------------------------------------------------------------

def test_opening_a_borrowing_also_commits_the_books_new_status(session):
    """The two writes share one commit. Committed separately, a crash between
    them would leave a book marked Available with a live loan against it.
    """
    repository = BorrowingRepository(session)
    user = add_user(session)
    book = add_book(session)

    borrowing = repository.open(
        book,
        user_id=user.id,
        status=BorrowingStatus.ACTIVE,
        book_status=BookStatus.BORROWED.value,
        due_date=utcnow() + datetime.timedelta(days=LOAN_PERIOD_DAYS),
    )

    session.expire_all()  # force a re-read, so this proves persistence
    assert session.get(books, book.id).status == BookStatus.BORROWED.value
    assert session.get(borrowings, borrowing.id).status == BorrowingStatus.ACTIVE.value


def test_an_open_borrowing_is_found_for_active_and_reserved_rows(session):
    repository = BorrowingRepository(session)
    user = add_user(session)

    active_book = add_book(session, title="Active")
    add_borrowing(session, active_book, user, BorrowingStatus.ACTIVE.value)
    reserved_book = add_book(session, title="Reserved")
    add_borrowing(session, reserved_book, user, BorrowingStatus.RESERVED.value)

    assert repository.get_open_for_book(active_book.id) is not None
    assert repository.get_open_for_book(reserved_book.id) is not None


def test_a_closed_borrowing_does_not_count_as_open(session):
    """Otherwise a returned book could never be borrowed again."""
    repository = BorrowingRepository(session)
    user = add_user(session)

    returned_book = add_book(session, title="Returned")
    add_borrowing(session, returned_book, user, BorrowingStatus.RETURNED.value)
    lost_book = add_book(session, title="Lost")
    add_borrowing(session, lost_book, user, BorrowingStatus.LOST.value)

    assert repository.get_open_for_book(returned_book.id) is None
    assert repository.get_open_for_book(lost_book.id) is None


def test_closing_a_borrowing_writes_both_rows(session):
    repository = BorrowingRepository(session)
    user = add_user(session)
    book = add_book(session, status=BookStatus.BORROWED.value)
    borrowing = add_borrowing(session, book, user)
    returned_at = utcnow()

    repository.close(
        borrowing,
        status=BorrowingStatus.RETURNED,
        book_status=BookStatus.AVAILABLE.value,
        return_date=returned_at,
    )

    session.expire_all()
    stored = session.get(borrowings, borrowing.id)
    assert stored.status == BorrowingStatus.RETURNED.value
    assert stored.return_date is not None
    assert session.get(books, book.id).status == BookStatus.AVAILABLE.value


def test_a_users_borrowings_come_back_newest_first(session):
    repository = BorrowingRepository(session)
    user = add_user(session)
    other = add_user(session, email="someone@example.com")
    first = add_borrowing(session, add_book(session, title="First"), user)
    second = add_borrowing(session, add_book(session, title="Second"), user)
    add_borrowing(session, add_book(session, title="Not Theirs"), other)

    result = repository.get_by_user(user.id)

    assert [row.id for row in result] == [second.id, first.id]


def test_deleting_a_book_removes_its_borrowings(session):
    """The cascade is what makes DELETE /books/{id} possible at all: with a
    foreign key pointing at the book and no cascade, the delete raises.
    """
    book_repository = BookRepository(session)
    user = add_user(session)
    book = add_book(session)
    borrowing = add_borrowing(session, book, user)

    assert book_repository.delete(book.id) is True

    assert session.get(books, book.id) is None
    assert session.get(borrowings, borrowing.id) is None


def test_deleting_a_user_removes_their_borrowings(session):
    user_repository = UserRepository(session)
    user = add_user(session)
    book = add_book(session)
    borrowing = add_borrowing(session, book, user)

    assert user_repository.delete(user.id) is True

    assert session.get(users, user.id) is None
    assert session.get(borrowings, borrowing.id) is None
    # The book outlives the borrower.
    assert session.get(books, book.id) is not None


# --------------------------------------------------------------------------
# BorrowingService against a real engine
# --------------------------------------------------------------------------

@pytest.fixture
def borrowing_service(session):
    return BorrowingService(BorrowingRepository(session), BookRepository(session))


def test_borrowing_sets_the_book_to_borrowed_and_a_due_date(borrowing_service, session):
    user = add_user(session)
    book = add_book(session)

    borrowing = borrowing_service.borrow(user.id, book.id)

    assert borrowing.status == BorrowingStatus.ACTIVE.value
    assert session.get(books, book.id).status == BookStatus.BORROWED.value
    # Naive UTC, matching the column type.
    expected = utcnow() + datetime.timedelta(days=LOAN_PERIOD_DAYS)
    assert abs((borrowing.due_date - expected).total_seconds()) < 10


def test_a_book_cannot_be_borrowed_twice(borrowing_service, session):
    first_user = add_user(session)
    second_user = add_user(session, email="second@example.com")
    book = add_book(session)

    borrowing_service.borrow(first_user.id, book.id)

    with pytest.raises(BookUnavailable):
        borrowing_service.borrow(second_user.id, book.id)


def test_borrowing_an_unknown_book_raises(borrowing_service, session):
    user = add_user(session)

    with pytest.raises(BookNotFound):
        borrowing_service.borrow(user.id, 404)


def test_reserving_leaves_no_due_date(borrowing_service, session):
    user = add_user(session)
    book = add_book(session)

    borrowing = borrowing_service.reserve(user.id, book.id)

    assert borrowing.status == BorrowingStatus.RESERVED.value
    assert borrowing.due_date is None
    assert session.get(books, book.id).status == BookStatus.RESERVED.value


def test_returning_frees_the_book_for_the_next_borrower(borrowing_service, session):
    user = add_user(session)
    other = add_user(session, email="next@example.com")
    book = add_book(session)
    borrowing = borrowing_service.borrow(user.id, book.id)

    returned = borrowing_service.return_book(user.id, borrowing.id)

    assert returned.status == BorrowingStatus.RETURNED.value
    assert returned.return_date is not None
    assert session.get(books, book.id).status == BookStatus.AVAILABLE.value
    # The whole point of freeing it.
    assert borrowing_service.borrow(other.id, book.id) is not None


def test_reporting_a_book_lost_writes_it_off(borrowing_service, session):
    user = add_user(session)
    book = add_book(session)
    borrowing = borrowing_service.borrow(user.id, book.id)

    lost = borrowing_service.report_lost(user.id, borrowing.id)

    assert lost.status == BorrowingStatus.LOST.value
    # It never came back, so recording a return date would be a lie.
    assert lost.return_date is None
    assert session.get(books, book.id).status == BookStatus.LOST.value


def test_a_lost_book_cannot_be_borrowed_again(borrowing_service, session):
    user = add_user(session)
    book = add_book(session)
    borrowing = borrowing_service.borrow(user.id, book.id)
    borrowing_service.report_lost(user.id, borrowing.id)

    with pytest.raises(BookUnavailable):
        borrowing_service.borrow(user.id, book.id)


def test_returning_someone_elses_borrowing_is_refused(borrowing_service, session):
    owner = add_user(session)
    stranger = add_user(session, email="stranger@example.com")
    book = add_book(session)
    borrowing = borrowing_service.borrow(owner.id, book.id)

    with pytest.raises(NotTheBorrower):
        borrowing_service.return_book(stranger.id, borrowing.id)

    assert session.get(books, book.id).status == BookStatus.BORROWED.value


def test_returning_the_same_borrowing_twice_is_refused(borrowing_service, session):
    user = add_user(session)
    book = add_book(session)
    borrowing = borrowing_service.borrow(user.id, book.id)
    borrowing_service.return_book(user.id, borrowing.id)

    with pytest.raises(BorrowingAlreadyClosed):
        borrowing_service.return_book(user.id, borrowing.id)


# --------------------------------------------------------------------------
# The whole API, end to end, on a real database
# --------------------------------------------------------------------------

CREDENTIALS = {"email": "reader@example.com", "password": "long-enough-password"}


def register_and_login(client):
    client.post(
        "/users/",
        json={**CREDENTIALS, "firstname": "Test", "lastname": "Reader"},
    )
    response = client.post("/auth/login", json=CREDENTIALS)
    assert response.status_code == 200, response.text
    body = response.json()
    return body["access_token"], body["user"]


def test_a_real_journey_from_signup_to_return(client):
    """One test that walks the whole feature the way a user would, with real
    rows, a real token and real status transitions.
    """
    token, user = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/books/",
        json={"title": "The Brothers Karamazov", "author": "Fyodor Dostoevsky", "year": 1880},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    book_id = created.json()["id"]
    assert created.json()["status"] == "Available"

    borrowed = client.post("/borrowings/borrow", json={"book_id": book_id}, headers=auth)
    assert borrowed.status_code == 201, borrowed.text
    borrowing_id = borrowed.json()["id"]
    assert client.get(f"/books/{book_id}").json()["status"] == "Borrowed"

    mine = client.get("/borrowings/me", headers=auth)
    assert [row["id"] for row in mine.json()] == [borrowing_id]
    row = mine.json()[0]
    # Nested so the frontend can render a title without a second request.
    assert row["book"]["title"] == "The Brothers Karamazov"
    assert row["user_id"] == user["id"]

    due = datetime.datetime.fromisoformat(row["due_date"])
    assert abs((due - (utcnow() + datetime.timedelta(days=LOAN_PERIOD_DAYS))).days) <= 1

    returned = client.post(f"/borrowings/{borrowing_id}/return", headers=auth)
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "Returned"
    assert client.get(f"/books/{book_id}").json()["status"] == "Available"


def test_borrowing_the_same_book_twice_conflicts_over_http(client):
    token, _ = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}
    book_id = client.post(
        "/books/",
        json={"title": "Only Copy", "author": "Anon", "year": 1999},
        headers=auth,
    ).json()["id"]

    first = client.post("/borrowings/borrow", json={"book_id": book_id}, headers=auth)
    assert first.status_code == 201
    second = client.post("/borrowings/borrow", json={"book_id": book_id}, headers=auth)

    assert second.status_code == 409


def test_creating_a_book_without_a_token_is_rejected(client):
    response = client.post(
        "/books/", json={"title": "Sneaky", "author": "Anon", "year": 2000}
    )

    assert response.status_code == 401


def test_search_over_http_hits_the_real_query(client):
    token, _ = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}
    for title, author in [("Crime and Punishment", "Dostoevsky"), ("War and Peace", "Tolstoy")]:
        client.post("/books/", json={"title": title, "author": author, "year": 1869}, headers=auth)

    found = client.get("/books/?q=dostoevsky")

    assert [book["title"] for book in found.json()] == ["Crime and Punishment"]


def test_paging_over_http_returns_one_row_at_a_time(client):
    token, _ = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}
    for index in range(3):
        client.post(
            "/books/",
            json={"title": f"Book {index}", "author": "Anon", "year": 2000},
            headers=auth,
        )

    first = client.get("/books/?skip=0&limit=1").json()
    second = client.get("/books/?skip=1&limit=1").json()

    assert len(first) == 1 and len(second) == 1
    assert first[0]["id"] != second[0]["id"]


def test_deleting_a_borrowed_book_over_http_succeeds(client):
    """A book with borrowing rows used to be undeletable; the cascade is what
    makes this a 204 rather than a foreign-key error.
    """
    token, _ = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}
    book_id = client.post(
        "/books/", json={"title": "Doomed", "author": "Anon", "year": 2000}, headers=auth
    ).json()["id"]
    client.post("/borrowings/borrow", json={"book_id": book_id}, headers=auth)

    deleted = client.delete(f"/books/{book_id}", headers=auth)

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/books/{book_id}").status_code == 404


def test_a_token_stops_working_once_its_user_is_deleted(client):
    """The per-request lookup is what closes the gap between a token's lifetime
    and its account's.
    """
    token, user = register_and_login(client)
    auth = {"Authorization": f"Bearer {token}"}

    assert client.delete(f"/users/{user['id']}", headers=auth).status_code == 204

    assert client.get("/users/me", headers=auth).status_code == 401


def test_health_reports_ok_against_a_live_database(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_registering_the_same_email_twice_conflicts(client):
    payload = {**CREDENTIALS, "firstname": "Test", "lastname": "Reader"}

    assert client.post("/users/", json=payload).status_code == 201
    assert client.post("/users/", json=payload).status_code == 409


def test_the_stored_password_is_hashed_not_plaintext(client, session):
    """Checked at the row, not through the API, because the response model
    hides the field either way.
    """
    client.post(
        "/users/", json={**CREDENTIALS, "firstname": "Test", "lastname": "Reader"}
    )

    stored = session.query(users).filter(users.email == CREDENTIALS["email"]).one()
    assert stored.password != CREDENTIALS["password"]
    assert stored.password.startswith("$2b$")
