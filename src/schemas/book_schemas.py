from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from src.models.enums import BookStatus

# Movable-type printing puts a floor under plausible publication years; the
# ceiling is computed per request so the suite does not start failing in January.
MIN_BOOK_YEAR = 1000
# Catalogue entries are sometimes created just before publication.
FUTURE_YEAR_GRACE = 1

MAX_TITLE_LENGTH = 300
MAX_AUTHOR_LENGTH = 200

# strip_whitespace before the length check, so "   " is rejected rather than
# stored as a blank row.
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_LENGTH),
]
Author = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_AUTHOR_LENGTH),
]


class BookCreate(BaseModel):
    title:  Title
    author: Author
    year:   int = Field(ge=MIN_BOOK_YEAR)

    @field_validator("year")
    @classmethod
    def reject_implausible_future_year(cls, value: int) -> int:
        latest = datetime.now(UTC).year + FUTURE_YEAR_GRACE
        if value > latest:
            raise ValueError(f"year must be {latest} or earlier")
        return value


class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title:  str
    author: str
    year:   int
    # Maintained by the borrowing lifecycle, not by clients.
    status: BookStatus
