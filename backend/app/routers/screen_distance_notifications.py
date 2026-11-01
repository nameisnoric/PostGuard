"""Ownership-safe, idempotent persistence for screen-distance reminders."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.screen_distance_notification import ScreenDistanceNotification
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.screen_distance_notification import (
    ScreenDistanceNotificationCreate,
    ScreenDistanceNotificationResponse,
)


router = APIRouter(tags=["Screen Distance Notifications"])


def _owned_session(session_id: int, db: Session, user_id: int) -> PostureSession:
    row = db.scalar(select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == user_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


@router.post(
    "/sessions/{session_id}/screen-distance-notifications",
    response_model=ScreenDistanceNotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_screen_distance_notification(
    session_id: int,
    request: ScreenDistanceNotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _owned_session(session_id, db, current_user.id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=409, detail="Screen reminders require a running session")
    query = select(ScreenDistanceNotification).where(
        ScreenDistanceNotification.session_id == session_id,
        ScreenDistanceNotification.runtime_notification_id == request.runtime_notification_id,
    )
    existing = db.scalar(query)
    if existing is not None:
        return existing
    row = ScreenDistanceNotification(
        session_id=session_id,
        runtime_notification_id=request.runtime_notification_id,
        alert_type=request.alert_type,
        distance_ratio=float(request.distance_ratio),
        decision=request.decision,
        reason=request.reason,
        emitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(query)
        if existing is not None:
            return existing
        raise
    db.refresh(row)
    return row


@router.get(
    "/sessions/{session_id}/screen-distance-notifications",
    response_model=list[ScreenDistanceNotificationResponse],
)
def get_screen_distance_notifications(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(session_id, db, current_user.id)
    return list(db.scalars(
        select(ScreenDistanceNotification)
        .where(ScreenDistanceNotification.session_id == session_id)
        .order_by(ScreenDistanceNotification.emitted_at.asc())
    ).all())
