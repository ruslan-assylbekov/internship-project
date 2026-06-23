from sqlalchemy.orm import Session
from core.models.database_models import books

class BookRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(books).all()

    def get_by_id(self, book_id: int):
        return self.db.query(books).filter(books.id == book_id).first()

    def create(self, book_data: dict):
        new_book = books(**book_data)
        self.db.add(new_book)
        self.db.commit()
        self.db.refresh(new_book)
        return new_book
