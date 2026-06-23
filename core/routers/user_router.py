from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database.database_connect import get_session
from core.repositories.user_repository import UserRepository
from core.schemas.user_schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["Users"])

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    repo = UserRepository(db)
    return repo.get_all()

@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    success = repo.get_by_id(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return success

@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    return repo.create(user.model_dump())

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    success = repo.delete(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User deleted"}