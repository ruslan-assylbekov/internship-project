from src.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, repository: BookRepository):
        self.repository = repository

    def get_all_books(
        self,
        skip: int = 0,
        limit: int = 50,
        q: str | None = None,
        status: str | None = None,
    ):
        return self.repository.get_all(skip=skip, limit=limit, q=q, status=status)

    def get_book_by_id(self, book_id: int):
        return self.repository.get_by_id(book_id)

    def create_book(self, book_data: dict):
        return self.repository.create(book_data)

    def delete_book(self, book_id: int):
        return self.repository.delete(book_id)
