from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import BorrowingStatus
from src.schemas.book_schemas import BookResponse


class BorrowingCreate(BaseModel):
    """Which book to act on. The borrower comes from the access token, never
    from the request body -- otherwise anyone could borrow on someone's behalf.
    """

    book_id: int = Field(gt=0)


class BorrowingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    book_id: int
    user_id: int
    status: BorrowingStatus
    borrow_date: datetime | None = None
    # Null for reservations, which are holds rather than loans.
    due_date: datetime | None = None
    return_date: datetime | None = None
    # Nested so the frontend can render a title without a second request.
    book: BookResponse | None = None
