from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.database import engine

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "PostGuard Backend is running"
    }


@router.get("/ready")
def readiness_check():
    """Confirm that the API can reach its required database."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostGuard Backend dependencies are unavailable",
        ) from exc

    return {
        "status": "ready",
        "database": "available",
    }
