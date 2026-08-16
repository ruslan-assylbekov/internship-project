"""Borrowing rules: what may be borrowed, returned, reserved or written off.

Distinct exceptions rather than falsy returns, because the caller has to tell
"no such book" (404) from "already on loan" (409) from "not yours" (403). The
HTTP mapping lives in the router, so this module stays transport-agnostic.
"""

from src.models.database_models import due_date_from, utcnow
from src.models.enums import BookStatus, BorrowingStatus
from src.repositories.book_repository import BookRepository
from src.repositories.borrowing_repository import BorrowingRepository


class BorrowingError(Exception):
    """Base for every rule this service enforces."""


class BookNotFound(BorrowingError):
    pass


class BorrowingNotFound(BorrowingError):
    pass


class BookUnavailable(BorrowingError):
    pass


class BorrowingAlreadyClosed(BorrowingError):
    pass


class NotTheBorrower(BorrowingError):
    pass


class BorrowingService:
    def __init__(
        self,
        repository: BorrowingRepository,
        book_repository: BookRepository,
    ):
        self.repository = repository
        self.book_repository = book_repository

    def get_all_borrowings(self, skip: int = 0, limit: int = 50):
        return self.repository.get_all(skip=skip, limit=limit)

    def get_borrowings_for_user(self, user_id: int, skip: int = 0, limit: int = 50):
        return self.repository.get_by_user(user_id, skip=skip, limit=limit)

    def borrow(self, user_id: int, book_id: int):
        book = self._available_book(book_id)
        borrowed_at = utcnow()
        return self.repository.open(
            book,
            user_id=user_id,
            status=BorrowingStatus.ACTIVE,
            book_status=BookStatus.BORROWED.value,
            due_date=due_date_from(borrowed_at),
        )

    def reserve(self, user_id: int, book_id: int):
        """A hold, not a loan: no due date until it is actually collected."""
        book = self._available_book(book_id)
        return self.repository.open(
            book,
            user_id=user_id,
            status=BorrowingStatus.RESERVED,
            book_status=BookStatus.RESERVED.value,
        )

    def return_book(self, user_id: int, borrowing_id: int):
        borrowing = self._open_borrowing_of(user_id, borrowing_id)
        return self.repository.close(
            borrowing,
            status=BorrowingStatus.RETURNED,
            book_status=BookStatus.AVAILABLE.value,
            return_date=utcnow(),
        )

    def report_lost(self, user_id: int, borrowing_id: int):
        """The book never comes back, so it is written off rather than returned
        to the shelf -- return_date stays null for the same reason.
        """
        borrowing = self._open_borrowing_of(user_id, borrowing_id)
        return self.repository.close(
            borrowing,
            status=BorrowingStatus.LOST,
            book_status=BookStatus.LOST.value,
        )

    def _available_book(self, book_id: int):
        book = self.book_repository.get_by_id(book_id)
        if book is None:
            raise BookNotFound(f"book {book_id} does not exist")

        # Two checks, because either one can be stale on its own: the column is
        # the fast answer, the open-row query is the authoritative one.
        if book.status != BookStatus.AVAILABLE.value:
            raise BookUnavailable(f"book {book_id} is {book.status}")
        if self.repository.get_open_for_book(book_id) is not None:
            raise BookUnavailable(f"book {book_id} is already spoken for")
        return book

    def _open_borrowing_of(self, user_id: int, borrowing_id: int):
        borrowing = self.repository.get_by_id(borrowing_id)
        if borrowing is None:
            raise BorrowingNotFound(f"borrowing {borrowing_id} does not exist")
        if borrowing.user_id != user_id:
            raise NotTheBorrower("that borrowing belongs to another user")
        if borrowing.status not in [s.value for s in BorrowingStatus.open_states()]:
            raise BorrowingAlreadyClosed(f"borrowing {borrowing_id} is {borrowing.status}")
        return borrowing
