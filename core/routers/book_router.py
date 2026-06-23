from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database.database_connect import get_session
from core.repositories.book_repository import BookRepository
from core.schemas.user_schemas import BookCreate, BookResponse

router = APIRouter(prefix="/books", tags=["Books"])

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[BookResponse])
def get_all_books(db: Session = Depends(get_db)):
    repo = BookRepository(db)
    return repo.get_all()

@router.get("/{book_id}", response_model=BookResponse)
def get_book_by_id(book_id: int, db: Session = Depends(get_db)):
    repo = BookRepository(db)
    return repo.get_by_id(book_id)

@router.post("/", response_model=BookResponse)
def create_book(book: BookCreate, db: Session = Depends(get_db)):
    repo = BookRepository(db)
    return repo.create(book.model_dump())
