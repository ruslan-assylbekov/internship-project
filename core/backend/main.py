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

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from core.database.database_connect import init_db, get_db_session, Session
from core.models.database_models import users, books, borrowings

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


@app.post("/users")
def create_user():
    pass


@app.get("/users/{user_id}")
def get_user(user_id: int, db: DBSession = Depends(get_db)):
    user = db.query(users).filter(users.id == user_id).first()
    return {"id": user.id, "email": user.email, "name": user.firstname}

#uvicorn core.backend.main:app --reload