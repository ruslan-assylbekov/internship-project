from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.core.security import MAX_PASSWORD_BYTES
from src.schemas.borrowing_schemas import BorrowingResponse


# What the client sends when creating a user
class UserCreate(BaseModel):
    email:     EmailStr
    password:  str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    firstname: str = Field(min_length=1, max_length=100)
    lastname:  str = Field(min_length=1, max_length=100)

# What the API returns (no password)
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    email:     str
    firstname: str
    lastname:  str
    created:   datetime


class UserDetailResponse(UserResponse):
    """A single user, with what they have borrowed.

    Used by ``/users/me`` and ``/users/{id}``; the list endpoint stays on
    ``UserResponse`` so browsing users does not drag every loan along. Defaults
    to empty rather than being required, so a caller serialising a plain dict
    does not have to supply it.
    """

    borrowings: list[BorrowingResponse] = []
