from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime

# What the client sends when creating a user
class UserCreate(BaseModel):
    email:     EmailStr
    password:  str
    firstname: str
    lastname:  str

# What the API returns (no password)
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:        int
    email:     str
    firstname: str
    lastname:  str
    created:   datetime

# class BorrowingCreate(BaseModel):
#     book_id: int
#     user_id: int
#     borrow_date: datetime
#     due_date: datetime