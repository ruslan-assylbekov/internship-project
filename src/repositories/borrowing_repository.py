import datetime

from sqlalchemy.orm import Session

from src.models.database_models import books, borrowings, utcnow
from src.models.enums import BorrowingStatus


class BorrowingRepository:
    """Persistence for borrowing rows.

    ``open`` and ``close`` also write ``books.status``. That crosses entities
    on purpose: a borrowing and the book state it implies must not be able to
    disagree, and committing them separately leaves a book marked Available
    while a loan exists. Both objects belong to the same Session -- routers get
    one per request -- so a single commit covers both.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 50):
        return (
            self.db.query(borrowings)
            .order_by(borrowings.id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, borrowing_id: int):
        return self.db.query(borrowings).filter(borrowings.id == borrowing_id).first()

    def get_by_user(self, user_id: int, skip: int = 0, limit: int = 50):
        return (
            self.db.query(borrowings)
            .filter(borrowings.user_id == user_id)
            .order_by(borrowings.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_open_for_book(self, book_id: int):
        """The loan or hold currently tying up a book, if any."""
        open_states = [state.value for state in BorrowingStatus.open_states()]
        return (
            self.db.query(borrowings)
            .filter(
                borrowings.book_id == book_id,
                borrowings.status.in_(open_states),
            )
            .first()
        )

    def open(
        self,
        book: books,
        user_id: int,
        status: BorrowingStatus,
        book_status: str,
        due_date: datetime.datetime | None = None,
    ) -> borrowings:
        borrowing = borrowings(
            book_id=book.id,
            user_id=user_id,
            status=status.value,
            borrow_date=utcnow(),
            due_date=due_date,
        )
        book.status = book_status
        self.db.add(borrowing)
        self.db.commit()
        self.db.refresh(borrowing)
        return borrowing

    def close(
        self,
        borrowing: borrowings,
        status: BorrowingStatus,
        book_status: str,
        return_date: datetime.datetime | None = None,
    ) -> borrowings:
        borrowing.status = status.value
        borrowing.return_date = return_date
        if borrowing.book is not None:
            borrowing.book.status = book_status
        self.db.commit()
        self.db.refresh(borrowing)
        return borrowing
