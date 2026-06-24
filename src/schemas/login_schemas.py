from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    