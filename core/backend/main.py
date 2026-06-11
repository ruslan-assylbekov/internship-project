#TODO
#
#CRUD functions for database
#pydantic validation
#docker
#
#
#clean architecture (i dont know)

import requests
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic_settings import BaseSettings

from core.database.database_connect import init_db, Session
from core.models.database_models import users, books, borrowings
from core.schemas.user_schemas import UserCreate, UserResponse, BookCreate, BorrowingCreate


class Settings(BaseSettings):
    api_key: str
    class Config:
        env_file = Path(__file__).parent.parent.parent / ".env"

settings = Settings()   # loads the .env file


app = FastAPI()

origins = ["http://127.0.0.1:8000", "http://localhost:63342"]

app.add_middleware(CORSMiddleware, 
    allow_origins = origins, # allow all origins from above
    allow_credentials=True,
    allow_methods=["*"], # allow all methods
    allow_headers=["*"],
    )

@app.on_event("startup")
def startup():
    init_db()

def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request) #момент когда запрос приходит на сайт
    duration = time.time() - start
    print(f"{request.method} {request.url.path} took {duration:0.4f} seconds")
    response.headers["request-process-time"] = f"{duration:.4f}" # можно вот так создавать свой header
    return response

@app.get("/")
def homepage():
    return FileResponse("index.html") # opens the html page. in pycharm you must open index.html through built in view

@app.get("/weather/{city}/{days}")
def get_weather(city: str, days: int):
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": settings.api_key, # get api from .env
        "q": city,
        "days": days,
        "hour": 0
    }
    response = requests.get(url, params=params) # sends request to weatherapi with those parameters
    data = response.json() # turn response into json
    forecast = ""
    for day in data["forecast"]["forecastday"]: # get temperature data from every forecast day
        forecast = forecast + str(day["date"]) +": "+  str(day["day"]["avgtemp_c"]) + "°C" + '\n'
    return {
        "city": data["location"]["name"],
        "temperature": data["current"]["temp_c"],
        "feeling": data["current"]["feelslike_c"],
        "clouds": data["current"]["condition"]["text"],
        "forecast": forecast
    }




@app.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    all_users = db.query(users).all()
    return all_users

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return db.query(users).filter(users.id == user_id).first()

@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = users(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # re-reads the row to get the generated id and created timestamp ?
    return new_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(users).filter(users.id == user_id).first() # first ?

    db.delete(user)
    db.commit()
    return {"detail": f"User {user_id} deleted"}





@app.get("/books")
def get_all_books(db: Session = Depends(get_db)):
    all_books = db.query(books).all()
    return all_books

@app.post("/books")
def create_book(book: BookCreate, db: Session = Depends(get_db)):
    new_book = books(**book.model_dump())
    db.add(new_book)
    db.commit()
    db.refresh(new_book)  # re-reads the row to get the generated id and created timestamp ?
    return new_book

@app.get("/books/{book_id}")
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(books).filter(books.id == book_id).first()
    return {"id": book.id, "title": book.title, "author": book.author, "year": book.year}

@app.post("/borrowings")
def borrow_book(borrowing: BorrowingCreate, db: Session = Depends(get_db)):
    new_borrow = borrowings(**borrowings.model_dump())
    db.add(new_borrow)
    db.commit()
    db.refresh(new_borrow)  # re-reads the row to get the generated id and created timestamp ?
    return new_borrow



#uvicorn core.backend.main:app --reload
#.venv\Scripts\activate