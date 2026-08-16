from pydantic import BaseModel, EmailStr

from src.schemas.user_schemas import UserResponse


class UserLogin(BaseModel):
    email: EmailStr
    # Deliberately unconstrained: login policy must not drift from signup
    # policy, and rejecting a long password here would leak which rule applies.
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """Token plus the authenticated user, so the frontend needs one request to
    log in and render a profile.
    """

    user: UserResponse
