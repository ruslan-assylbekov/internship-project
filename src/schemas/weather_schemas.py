from pydantic import BaseModel


class WeatherResponse(BaseModel):
    city:     str
    temperature:  float
    feeling: float
    clouds:  str
