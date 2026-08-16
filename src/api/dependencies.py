"""Shared FastAPI dependency chains.

Kept in one place so that routers needing the same service (e.g. users and
auth) wire it identically. Routers re-export what they use, so overriding
``src.api.user_router.get_user_service`` in tests still works.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.database.database_connect import get_session
from src.core.security import decode_access_token
from src.repositories.book_repository import BookRepository
from src.repositories.borrowing_repository import BorrowingRepository
from src.repositories.user_repository import UserRepository
from src.services.book_service import BookService
from src.services.borrowing_service import BorrowingService
from src.services.user_service import UserService

# tokenUrl is relative on purpose: it keeps the Swagger "Authorize" button
# working behind a path prefix or a proxy.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_user_repository(db: Session = Depends(get_session)) -> UserRepository:
    return UserRepository(db)


def get_user_service(
    repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repository)


def get_book_repository(db: Session = Depends(get_session)) -> BookRepository:
    return BookRepository(db)


def get_book_service(
    repository: BookRepository = Depends(get_book_repository),
) -> BookService:
    return BookService(repository)


def get_borrowing_repository(
    db: Session = Depends(get_session),
) -> BorrowingRepository:
    return BorrowingRepository(db)


def get_borrowing_service(
    repository: BorrowingRepository = Depends(get_borrowing_repository),
    book_repository: BookRepository = Depends(get_book_repository),
) -> BorrowingService:
    # Both repositories resolve the same Session: FastAPI caches get_session
    # per request, which is what lets a borrow update two tables in one commit.
    return BorrowingService(repository, book_repository)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    service: UserService = Depends(get_user_service),
):
    """Resolve the bearer token to a user row, or reject the request.

    Every failure -- malformed, expired, wrong signature, deleted user -- is the
    same 401 with the same message, so the response cannot be used to probe
    which tokens or accounts exist.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    subject = payload.get("sub")
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise credentials_error from None

    # Looked up every request rather than trusted from the token, so deleting a
    # user takes effect immediately instead of at token expiry.
    user = service.get_user_by_id(user_id)
    if user is None:
        raise credentials_error
    return user
