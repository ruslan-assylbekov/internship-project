from fastapi import FastAPI
import requests

app = FastAPI()

API_KEY = "0acc9d47af6d4897955121059261003"


@app.get("/")
def root():
    return {"Heloworld"}


@app.get("/weather/{city}")
def get_weather(city: str):
    url = "http://api.weatherapi.com/v1/current.json"
    params = {
        "key": API_KEY,
        "q": city
    }
    response = requests.get(url, params=params)

    return response.json()


