from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import timezone, datetime

from app.database.database import get_db
from app.models.alert_event import AlertEvent
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.alert_event import AlertEventCreate, AlertEventResponse

router = APIRouter(
    tags=["Alert Events"]
)

@router.post(
    "/sessions/{session_id}/alerts",
    response_model=AlertEventResponse,
    status_code=status.HTTP_201_CREATED
)
def create_alert_event(
    session_id: int,
    request: AlertEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(session_statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    if posture_session.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alerts can only be created during a running session"
        )

    active_alert_statement = select(AlertEvent).where(
        AlertEvent.session_id == session_id,
        AlertEvent.event_type == request.event_type,
        AlertEvent.ended_at.is_(None)
    )

    active_alert = db.scalar(active_alert_statement)

    if active_alert is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active alert of this type already exists"
        )

    alert_event = AlertEvent(
        session_id=session_id,
        event_type=request.event_type,
        risk_level=request.risk_level,
        started_at=datetime.now(timezone.utc),
        duration=0
    )

    db.add(alert_event)
    db.commit()
    db.refresh(alert_event)

    return alert_event

@router.post(
    "/alerts/{event_id}/end",
    response_model=AlertEventResponse,
    status_code=status.HTTP_200_OK
)
def end_alert_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(AlertEvent)
        .join(
            PostureSession,
            AlertEvent.session_id == PostureSession.session_id
        )
        .where(
            AlertEvent.event_id == event_id,
            PostureSession.user_id == current_user.id
        )
    )

    alert_event = db.scalar(statement)

    if alert_event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert event not found"
        )

    if alert_event.ended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Alert event has already ended"
        )

    now = datetime.now(timezone.utc)

    duration_seconds = int(
        (now - alert_event.started_at).total_seconds()
    )

    alert_event.ended_at = now
    alert_event.duration = duration_seconds

    db.commit()
    db.refresh(alert_event)

    return alert_event

@router.get(
    "/sessions/{session_id}/alerts",
    response_model=list[AlertEventResponse],
    status_code=status.HTTP_200_OK
)
def get_session_alerts(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_statement = select(PostureSession).where(
        PostureSession.session_id == session_id,
        PostureSession.user_id == current_user.id
    )

    posture_session = db.scalar(session_statement)

    if posture_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    alert_statement = (
        select(AlertEvent)
        .where(
            AlertEvent.session_id == session_id
        )
        .order_by(
            AlertEvent.started_at.asc()
        )
    )

    alert_events = db.scalars(alert_statement).all()

    return alert_events

@router.get(
    "/alerts/{event_id}",
    response_model=AlertEventResponse,
    status_code=status.HTTP_200_OK
)
def get_alert_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    statement = (
        select(AlertEvent)
        .join(
            PostureSession,
            AlertEvent.session_id == PostureSession.session_id
        )
        .where(
            AlertEvent.event_id == event_id,
            PostureSession.user_id == current_user.id
        )
    )

    alert_event = db.scalar(statement)

    if alert_event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert event not found"
        )

    return alert_event