from pydantic import BaseModel, ConfigDict

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