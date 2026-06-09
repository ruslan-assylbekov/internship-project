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
from pydantic import BaseModel

app = FastAPI()

origins = ["http://127.0.0.1:8000", "http://localhost:3000"]

API_KEY = "0acc9d47af6d4897955121059261003"

app.add_middleware(CORSMiddleware, allow_origins = origins)


@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request) #момент когда запрос приходит на сайт
    duration = time.time() - start
    # print(request.headers.get("User-Agent"))
    print(f"{request.method} {request.url.path} took {duration:0.4f} seconds")
    response.headers["request-process-time"] = str(duration)
    return response

# @app.get("/")
# def homepage():
#     return FileResponse("index.html")

@app.get("/weather/{city}")
def get_weather(city: str):
    url = "http://api.weatherapi.com/v1/current.json"
    params = {
        "key": API_KEY,
        "q": city
    }
    response = requests.get(url, params=params)

    data = response.json()
    return {
        "city": data["location"]["name"],
        "temperature": data["current"]["temp_c"],
        "feeling": data["current"]["feelslike_c"],
        "clouds": data["current"]["condition"]["text"]
    }





#uvicorn main:app --reload