from fastapi import FastAPI
import requests
from fastapi.responses import FileResponse

app = FastAPI()

API_KEY = "0acc9d47af6d4897955121059261003"

@app.get("/")
def homepage():
    return FileResponse("index.html")

# @app.get("/")
# def root():
#     return {"Heloworld"}

@app.get("/weather")
def get_weather():
    url = "http://api.weatherapi.com/v1/current.json"
    params = {
        "key": API_KEY,
        "q": "London"
    }
    response = requests.get(url, params=params)
    return response.json()


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
        "temperature_c": data["current"]["temp_c"],
        "condition": data["current"]["condition"]["text"],
        "humidity": data["current"]["humidity"]
    }


#uvicorn main:app --reload