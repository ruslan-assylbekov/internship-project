import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

from src.models.enums import BookStatus, BorrowingStatus

Base = declarative_base()  # base for database models

# A borrowed book is due back this many days later.
LOAN_PERIOD_DAYS = 14


def utcnow() -> datetime.datetime:
    """Naive UTC timestamp.

    Replaces the deprecated ``datetime.utcnow``. The columns below are
    ``DateTime`` (no timezone), so the offset is dropped to keep the stored
    value byte-identical to what ``utcnow`` produced -- switching the columns
    to ``DateTime(timezone=True)`` would need a migration that reinterprets
    existing rows against the server timezone.
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def due_date_from(borrowed_at: datetime.datetime) -> datetime.datetime:
    return borrowed_at + datetime.timedelta(days=LOAN_PERIOD_DAYS)


class users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    password = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    created = Column(DateTime, default=utcnow)

    # Eager so that serialising a user's borrowings is one extra query rather
    # than one per row. Cascade because a user row cannot be deleted while
    # borrowings still reference it.
    borrowings = relationship(
        "borrowings",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

class books(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    author = Column(String)
    year = Column(Integer, default = 0)
    status = Column(String, default = BookStatus.AVAILABLE.value)
    created = Column(DateTime, default=utcnow)

    # Lazy: the catalogue listing does not need borrowing rows, and this
    # relationship exists mainly so deleting a book clears them.
    borrowings = relationship(
        "borrowings",
        back_populates="book",
        cascade="all, delete-orphan",
    )

class borrowings(Base):
    __tablename__ = 'borrowings'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    borrow_date = Column(DateTime, default=utcnow)
    return_date = Column(DateTime)
    # Distinguishes a loan from a hold and an open row from a closed one;
    # return_date alone cannot express "reserved" or "lost".
    status = Column(
        String,
        nullable=False,
        default=BorrowingStatus.ACTIVE.value,
        server_default=BorrowingStatus.ACTIVE.value,
    )
    # Null for reservations, which are holds rather than loans.
    due_date = Column(DateTime)

    user = relationship("users", back_populates="borrowings")
    # Joined: every borrowing is rendered with its book's title.
    book = relationship("books", back_populates="borrowings", lazy="joined")
