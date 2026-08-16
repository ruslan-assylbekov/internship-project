from fastapi import APIRouter, Depends, HTTPException, Query, Response

from src.api.dependencies import get_book_repository, get_book_service, get_current_user
from src.api.pagination import Pagination
from src.models.enums import BookStatus
from src.schemas.book_schemas import BookCreate, BookResponse
from src.services.book_service import BookService

__all__ = ["router", "get_book_repository", "get_book_service", "get_current_user"]

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("/", response_model=list[BookResponse])
def get_all_books(
    page: Pagination = Depends(),
    q: str | None = Query(None, min_length=1, max_length=100,
                          description="Match against title or author."),
    status: BookStatus | None = Query(None, description="Filter by availability."),
    service: BookService = Depends(get_book_service),
):
    """Browse the catalogue. Reading it stays public; changing it does not."""
    return service.get_all_books(skip=page.skip, limit=page.limit, q=q, status=status)

@router.get("/{book_id}", response_model=BookResponse)
def get_book_by_id(book_id: int, service: BookService = Depends(get_book_service)):
    book = service.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/", response_model=BookResponse, status_code=201,
             dependencies=[Depends(get_current_user)])
def create_book(book: BookCreate, service: BookService = Depends(get_book_service)):
    return service.create_book(book.model_dump())

@router.delete("/{book_id}", status_code=204, response_class=Response,
               dependencies=[Depends(get_current_user)])
def delete_book(book_id: int, service: BookService = Depends(get_book_service)):
    """204 rather than a body: there is nothing left to describe, and every
    delete in this API answers the same way.
    """
    success = service.delete_book(book_id)
    if not success:
        raise HTTPException(status_code=404, detail="Book not found")
    return Response(status_code=204)
