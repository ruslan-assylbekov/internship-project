"""Liveness/readiness probe.

Reports on the dependency that actually stops the app from working: the
database. Anything orchestrating this container (compose, a deploy target)
needs a URL that fails when the app cannot serve traffic, not merely when the
process is up.
"""

import logging

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.database.database_connect import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health(response: Response, db: Session = Depends(get_session)):
    """200 when the database answers, 503 when it does not.

    Returns a body either way -- a probe that only sees a status code is
    harder to debug than one that says which check failed. 503 is set on the
    response rather than raised so the shape stays identical in both cases.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("health check could not reach the database", extra={"error": str(exc)})
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unreachable")

    return HealthResponse(status="ok", database="ok")
