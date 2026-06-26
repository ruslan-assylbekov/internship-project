from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database.database_connect import get_session
from src.repositories.book_repository import BookRepository
from src.schemas.book_schemas import BookCreate, BookResponse
from src.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["Books"])

def get_book_repository(db: Session = Depends(get_session)):
    return BookRepository(db)

def get_book_service(repository: BookRepository = Depends(get_book_repository)):
    return BookService(repository)

@router.get("/", response_model=list[BookResponse])
def get_all_books(service: BookService = Depends(get_book_service)):
    return service.get_all_books()

@router.get("/{book_id}", response_model=BookResponse)
def get_book_by_id(book_id: int, service: BookService = Depends(get_book_service)):
    book = service.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/", response_model=BookResponse)
def create_book(book: BookCreate, service: BookService = Depends(get_book_service)):
    return service.create_book(book.model_dump())

@router.delete("/{book_id}")
def delete_book(book_id: int, service: BookService = Depends(get_book_service)):
    success = service.delete_book(book_id)
    if not success:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"detail": "Book deleted"}
