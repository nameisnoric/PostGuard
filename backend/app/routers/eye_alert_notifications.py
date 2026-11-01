"""Ownership-safe and idempotent persistence for eye reminders."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.eye_alert_notification import EyeAlertNotification
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.eye_alert_notification import (
    EyeAlertNotificationCreate,
    EyeAlertNotificationResponse,
)


router = APIRouter(tags=["Eye Alert Notifications"])


def _owned_session(session_id: int, db: Session, user_id: int) -> PostureSession:
    row = db.scalar(select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == user_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


@router.post(
    "/sessions/{session_id}/eye-alert-notifications",
    response_model=EyeAlertNotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_eye_alert_notification(
    session_id: int,
    request: EyeAlertNotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _owned_session(session_id, db, current_user.id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=409, detail="Eye reminders require a running session")
    existing = db.scalar(select(EyeAlertNotification).where(
        EyeAlertNotification.session_id == session_id,
        EyeAlertNotification.runtime_notification_id == request.runtime_notification_id,
    ))
    if existing is not None:
        return existing
    row = EyeAlertNotification(
        session_id=session_id,
        runtime_notification_id=request.runtime_notification_id,
        alert_type=request.alert_type,
        blink_rate=float(request.blink_rate),
        window_blink_count=request.window_blink_count,
        decision=request.decision,
        reason=request.reason,
        emitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(EyeAlertNotification).where(
            EyeAlertNotification.session_id == session_id,
            EyeAlertNotification.runtime_notification_id == request.runtime_notification_id,
        ))
        if existing is not None:
            return existing
        raise
    db.refresh(row)
    return row


@router.get(
    "/sessions/{session_id}/eye-alert-notifications",
    response_model=list[EyeAlertNotificationResponse],
)
def get_eye_alert_notifications(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(session_id, db, current_user.id)
    return list(db.scalars(
        select(EyeAlertNotification)
        .where(EyeAlertNotification.session_id == session_id)
        .order_by(EyeAlertNotification.emitted_at.asc())
    ).all())
