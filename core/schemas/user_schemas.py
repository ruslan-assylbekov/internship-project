from pydantic import BaseModel, EmailStr
from datetime import datetime


# What the client sends when creating a user
class UserCreate(BaseModel):
    email:     EmailStr
    password:  str
    firstname: str
    lastname:  str

# What the API returns (no password)
class UserResponse(BaseModel):
    id:        int
    email:     str
    firstname: str
    lastname:  str
    created:   datetime

    class Config:
        from_attributes = True  # lets Pydantic read SQLAlchemy objects directly

class BookCreate(BaseModel):
    title:  str
    author: str
    year:   int

class BorrowingCreate(BaseModel):
    book_id: int
    user_id: int
    borrow_date: datetime
    due_date: datetime

