from fastapi import FastAPI
import requests
import time
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

API_KEY = "0acc9d47af6d4897955121059261003"

@app.middleware("http")
async def log_requests(request, call_next):
    start = time.time()
    response = await call_next(request) #момент когда запрос приходит на сайт
    duration = time.time() - start
    print(request.headers.get("User-Agent"))
    print(f"{request.method} {request.url.path} took {duration:0.4f} seconds")
    return response

@app.get("/")
def homepage():
    return FileResponse("index.html")

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
        "country": data["location"]["country"],
        "temperature": data["current"]["temp_c"],
        "condition": data["current"]["condition"]["text"],
        "humidity": data["current"]["humidity"]
    }


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:3000"
#     ],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


#uvicorn main:app --reload