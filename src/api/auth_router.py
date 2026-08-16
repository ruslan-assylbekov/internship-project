from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.dependencies import get_current_user, get_user_service
from src.core.security import create_access_token
from src.schemas.login_schemas import LoginResponse, Token, UserLogin
from src.schemas.user_schemas import UserDetailResponse
from src.services.user_service import UserService

__all__ = ["router", "get_current_user", "get_user_service"]

router = APIRouter(prefix="/auth", tags=["Auth"])

INVALID_CREDENTIALS = "Invalid email or password"


@router.post("/login", response_model=LoginResponse)
def login(credentials: UserLogin, service: UserService = Depends(get_user_service)):
    """Verify credentials and issue an access token.

    The user is returned alongside the token so the frontend can render a
    profile without a follow-up request. ``UserResponse`` omits the password
    hash, which is what makes returning the row here safe.
    """
    user = service.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )
    return LoginResponse(access_token=create_access_token(user.id), user=user)


@router.post("/token", response_model=Token)
def issue_token(form: OAuth2PasswordRequestForm = Depends(),
                service: UserService = Depends(get_user_service)):
    """Standard OAuth2 password-grant form endpoint.

    Exists so the /docs "Authorize" button works; it carries the email in the
    spec-mandated ``username`` field. /auth/login is the JSON equivalent.
    """
    user = service.authenticate(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserDetailResponse)
def read_current_user(current_user=Depends(get_current_user)):
    """Who the caller is, according to their token.

    Mirrors /users/me; both exist because the frontend asks "am I still logged
    in?" against /auth and "show my profile" against /users.
    """
    return current_user
