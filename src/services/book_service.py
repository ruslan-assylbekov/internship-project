from src.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, repository: BookRepository):
        self.repository = repository

    def get_all_books(self):
        return self.repository.get_all()

    def get_book_by_id(self, book_id: int):
        return self.repository.get_by_id(book_id)

    def create_book(self, book_data: dict):
        return self.repository.create(book_data)

    def delete_book(self, book_id: int):
        return self.repository.delete(book_id)
