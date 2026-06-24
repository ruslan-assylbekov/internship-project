from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime


class WeatherResponse(BaseModel):
    city:     str
    temperature:  float
    feeling: float
    clouds:  str

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

class BookCreate(BaseModel):
    title:  str
    author: str
    year:   int

class BookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title:  str
    author: str
    year:   int

class BorrowingCreate(BaseModel):
    book_id: int
    user_id: int
    borrow_date: datetime
    due_date: datetime

