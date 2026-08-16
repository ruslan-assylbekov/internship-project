from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models.database_models import books


class BookRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        q: str | None = None,
        status: str | None = None,
    ):
        """A page of the catalogue, optionally filtered.

        ``q`` matches title or author case-insensitively; ``%`` and ``_`` in it
        are escaped so a user searching for "100%" does not get a wildcard.
        """
        query = self.db.query(books)

        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            query = query.filter(
                or_(
                    books.title.ilike(pattern, escape="\\"),
                    books.author.ilike(pattern, escape="\\"),
                )
            )
        if status:
            query = query.filter(books.status == str(status))

        # Explicit order: without one, offset/limit may return overlapping pages.
        return query.order_by(books.id).offset(skip).limit(limit).all()

    def get_by_id(self, book_id: int):
        return self.db.query(books).filter(books.id == book_id).first()

    def create(self, book_data: dict):
        new_book = books(**book_data)
        self.db.add(new_book)
        self.db.commit()
        self.db.refresh(new_book)
        return new_book

    def delete(self, book_id: int):
        book = self.get_by_id(book_id)
        if book:
            # Borrowing rows reference this book; the relationship cascade
            # clears them, otherwise the delete trips the foreign key.
            self.db.delete(book)
            self.db.commit()
            return True
        return False
