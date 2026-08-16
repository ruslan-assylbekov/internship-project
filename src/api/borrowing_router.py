from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_borrowing_service, get_current_user
from src.api.pagination import Pagination
from src.schemas.borrowing_schemas import BorrowingCreate, BorrowingResponse
from src.services.borrowing_service import (
    BookNotFound,
    BookUnavailable,
    BorrowingAlreadyClosed,
    BorrowingError,
    BorrowingNotFound,
    BorrowingService,
    NotTheBorrower,
)

__all__ = ["router", "get_borrowing_service", "get_current_user"]

router = APIRouter(prefix="/borrowings", tags=["Borrowings"])

# The service raises domain errors; turning them into status codes is the
# router's job, and doing it through one table keeps the four handlers below
# from each inventing their own mapping.
STATUS_FOR_ERROR = {
    BookNotFound: status.HTTP_404_NOT_FOUND,
    BorrowingNotFound: status.HTTP_404_NOT_FOUND,
    BookUnavailable: status.HTTP_409_CONFLICT,
    BorrowingAlreadyClosed: status.HTTP_409_CONFLICT,
    NotTheBorrower: status.HTTP_403_FORBIDDEN,
}


def as_http_error(exc: BorrowingError) -> HTTPException:
    code = STATUS_FOR_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/", response_model=list[BorrowingResponse])
def get_all_borrowings(
    page: Pagination = Depends(),
    _=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    """Every borrowing. Authenticated because it exposes who has what."""
    return service.get_all_borrowings(skip=page.skip, limit=page.limit)


@router.get("/me", response_model=list[BorrowingResponse])
def get_my_borrowings(
    page: Pagination = Depends(),
    current_user=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    return service.get_borrowings_for_user(
        current_user.id, skip=page.skip, limit=page.limit
    )


@router.post("/borrow", response_model=BorrowingResponse, status_code=201)
def borrow_book(
    payload: BorrowingCreate,
    current_user=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    """Take a book out. The borrower is the token holder, not a body field."""
    try:
        return service.borrow(current_user.id, payload.book_id)
    except BorrowingError as exc:
        raise as_http_error(exc) from exc


@router.post("/reserve", response_model=BorrowingResponse, status_code=201)
def reserve_book(
    payload: BorrowingCreate,
    current_user=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    try:
        return service.reserve(current_user.id, payload.book_id)
    except BorrowingError as exc:
        raise as_http_error(exc) from exc


@router.post("/{borrowing_id}/return", response_model=BorrowingResponse)
def return_book(
    borrowing_id: int,
    current_user=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    try:
        return service.return_book(current_user.id, borrowing_id)
    except BorrowingError as exc:
        raise as_http_error(exc) from exc


@router.post("/{borrowing_id}/report-lost", response_model=BorrowingResponse)
def report_lost(
    borrowing_id: int,
    current_user=Depends(get_current_user),
    service: BorrowingService = Depends(get_borrowing_service),
):
    try:
        return service.report_lost(current_user.id, borrowing_id)
    except BorrowingError as exc:
        raise as_http_error(exc) from exc
