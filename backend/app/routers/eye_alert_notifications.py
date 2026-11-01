from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
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


def _owned_session(*, session_id: int, db: Session, current_user: User) -> PostureSession:
    row = db.scalar(
        select(PostureSession).where(
            PostureSession.session_id == session_id,
            PostureSession.user_id == current_user.id,
        )
    )
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
    session = _owned_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )
    if session.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Eye reminders can only be created while the session is RUNNING",
        )

    row = EyeAlertNotification(
        session_id=session_id,
        alert_type=request.alert_type,
        blink_rate=float(request.blink_rate),
        window_blink_count=request.window_blink_count,
        decision=request.decision,
        reason=request.reason,
        emitted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/sessions/{session_id}/eye-alert-notifications",
    response_model=list[EyeAlertNotificationResponse],
)
def get_session_eye_alert_notifications(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )
    return list(
        db.scalars(
            select(EyeAlertNotification)
            .where(EyeAlertNotification.session_id == session_id)
            .order_by(EyeAlertNotification.emitted_at.asc())
        ).all()
    )
