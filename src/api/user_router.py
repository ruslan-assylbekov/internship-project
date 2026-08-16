from fastapi import APIRouter, Depends, HTTPException, Response

from src.api.dependencies import get_current_user, get_user_repository, get_user_service
from src.api.pagination import Pagination
from src.schemas.user_schemas import UserCreate, UserDetailResponse, UserResponse
from src.services.user_service import UserService

__all__ = ["router", "get_user_repository", "get_user_service", "get_current_user"]

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/", response_model=list[UserResponse])
def get_all_users(
    page: Pagination = Depends(),
    service: UserService = Depends(get_user_service),
):
    return service.get_all_users(skip=page.skip, limit=page.limit)

# Declared before /{user_id}: registered the other way round, "me" would be
# matched as a user id and rejected as a non-integer.
@router.get("/me", response_model=UserDetailResponse)
def get_current_user_profile(current_user=Depends(get_current_user)):
    """The caller's own profile, including what they have borrowed."""
    return current_user

@router.get("/{user_id}", response_model=UserDetailResponse)
def get_user_by_id(user_id: int, service: UserService = Depends(get_user_service)):
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=201)
def create_user(user: UserCreate, service: UserService = Depends(get_user_service)):
    if service.get_user_by_email(user.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    return service.create_user(user.model_dump())

@router.delete("/{user_id}", status_code=204, response_class=Response)
def delete_user(
    user_id: int,
    current_user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """Self-service only. There is no role model yet, so the safe rule is that
    a token authorises deleting its own account and nothing else.
    """
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You may only delete your own account")
    success = service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=204)
