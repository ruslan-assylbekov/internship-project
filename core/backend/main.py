#TODO
#
#check the CORS
#pydantic validation
#env
#clean architecture


from fastapi import FastAPI
import requests
import time
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str

    class Config:
        env_file = ".env"

settings = Settings()   # loads the .env file


app = FastAPI()

origins = ["http://127.0.0.1:8000", "http://localhost:3000"]


app.add_middleware(CORSMiddleware, 
    allow_origins = origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    )


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request) #момент когда запрос приходит на сайт
    duration = time.time() - start
    # print(request.headers.get("User-Agent"))
    print(f"{request.method} {request.url.path} took {duration:0.4f} seconds")
    response.headers["request-process-time"] = f"{duration:.4f}"
    return response

@app.get("/")
def homepage():
    return FileResponse("index.html")



@app.get("/weather/{city}/{days}")
def get_weather(city: str, days: int):
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": settings.api_key,
        "q": city,
        "days": days,
        "hour": 0
    }

    response = requests.get(url, params=params)
    data = response.json()
    forecast = ""
    for day in data["forecast"]["forecastday"]:
        forecast = forecast + str(day["date"]) +": "+  str(day["day"]["avgtemp_c"]) + "°C" + '\n'


    return {
        "city": data["location"]["name"],
        "temperature": data["current"]["temp_c"],
        "feeling": data["current"]["feelslike_c"],
        "clouds": data["current"]["condition"]["text"],
        "forecast": forecast
    }


#uvicorn main:app --reload