"""Ownership-safe, idempotent persistence for risk episodes and notifications."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.alert_notification import AlertNotification
from app.models.risk_event import RiskEvent
from app.models.session import PostureSession
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.risk_persistence import (
    AlertNotificationCreate,
    AlertNotificationResponse,
    RiskEventResolve,
    RiskEventResponse,
    RiskEventStart,
    RiskEventUpdate,
)
from app.services.risk_events import elapsed_seconds, update_max_level


router = APIRouter(tags=["Risk Persistence"])
UPDATE_ACTIONS = {"UPDATED", "ESCALATED", "DEESCALATED", "DATA_GAP"}
ALERT_TYPES = {"FIRST", "REPEAT", "ESCALATION", "RESOLUTION"}


def _owned_session(db: Session, session_id: int, user_id: int) -> PostureSession:
    session = db.scalar(
        select(PostureSession).where(
            PostureSession.session_id == session_id,
            PostureSession.user_id == user_id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _event(db: Session, session_id: int, runtime_event_id: str) -> RiskEvent:
    event = db.scalar(
        select(RiskEvent).where(
            RiskEvent.session_id == session_id,
            RiskEvent.runtime_event_id == runtime_event_id,
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Risk event not found")
    return event


@router.post(
    "/sessions/{session_id}/risk-events",
    response_model=RiskEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_risk_event(
    session_id: int,
    request: RiskEventStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _owned_session(db, session_id, current_user.id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=409, detail="Risk events require a running session")
    existing = db.scalar(
        select(RiskEvent).where(
            RiskEvent.session_id == session_id,
            RiskEvent.runtime_event_id == request.runtime_event_id,
        )
    )
    if existing is not None:
        return existing
    now = datetime.now(timezone.utc)
    event = RiskEvent(
        session_id=session_id,
        runtime_event_id=request.runtime_event_id,
        initial_risk_level=request.risk_level.value,
        current_risk_level=request.risk_level.value,
        max_risk_level=request.risk_level.value,
        status="ACTIVE",
        started_at=now,
        duration_seconds=0.0,
        active_factors=request.active_factors,
        evidence_groups=request.evidence_groups,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(RiskEvent).where(
                RiskEvent.session_id == session_id,
                RiskEvent.runtime_event_id == request.runtime_event_id,
            )
        )
        if existing is not None:
            return existing
        raise
    db.refresh(event)
    return event


@router.patch(
    "/sessions/{session_id}/risk-events/{runtime_event_id}",
    response_model=RiskEventResponse,
)
def update_risk_event(
    session_id: int,
    runtime_event_id: str,
    request: RiskEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _owned_session(db, session_id, current_user.id)
    if session.status not in ("RUNNING", "PAUSED"):
        raise HTTPException(status_code=409, detail="Session is inactive")
    if request.event_action not in UPDATE_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported risk event action")
    event = _event(db, session_id, runtime_event_id)
    if event.status != "ACTIVE":
        return event
    now = datetime.now(timezone.utc)
    event.current_risk_level = request.risk_level.value
    update_max_level(event, request.risk_level.value)
    event.active_factors = request.active_factors
    event.evidence_groups = request.evidence_groups
    event.duration_seconds = elapsed_seconds(event.started_at, now)
    db.commit()
    db.refresh(event)
    return event


@router.post(
    "/sessions/{session_id}/risk-events/{runtime_event_id}/resolve",
    response_model=RiskEventResponse,
)
def resolve_risk_event(
    session_id: int,
    runtime_event_id: str,
    request: RiskEventResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(db, session_id, current_user.id)
    event = _event(db, session_id, runtime_event_id)
    if event.status == "RESOLVED":
        return event
    now = datetime.now(timezone.utc)
    event.status = "RESOLVED"
    event.ended_at = now
    event.duration_seconds = elapsed_seconds(event.started_at, now)
    event.resolved_reason = request.resolved_reason
    db.commit()
    db.refresh(event)
    return event


@router.post(
    "/sessions/{session_id}/risk-events/{runtime_event_id}/notifications",
    response_model=AlertNotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_alert_notification(
    session_id: int,
    runtime_event_id: str,
    request: AlertNotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _owned_session(db, session_id, current_user.id)
    if session.status not in ("RUNNING", "PAUSED"):
        raise HTTPException(status_code=409, detail="Session is inactive")
    if request.alert_type not in ALERT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported alert type")
    existing = db.scalar(
        select(AlertNotification).where(
            AlertNotification.session_id == session_id,
            AlertNotification.runtime_notification_id == request.runtime_notification_id,
        )
    )
    if existing is not None:
        return existing
    event = _event(db, session_id, runtime_event_id)
    notification = AlertNotification(
        risk_event_id=event.risk_event_id,
        session_id=session_id,
        runtime_notification_id=request.runtime_notification_id,
        alert_type=request.alert_type,
        risk_level=request.risk_level.value if request.risk_level else None,
        decision=request.decision,
        reason=request.reason,
    )
    db.add(notification)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(AlertNotification).where(
                AlertNotification.session_id == session_id,
                AlertNotification.runtime_notification_id
                == request.runtime_notification_id,
            )
        )
        if existing is not None:
            return existing
        raise
    db.refresh(notification)
    return notification


@router.get(
    "/sessions/{session_id}/risk-events",
    response_model=list[RiskEventResponse],
)
def get_session_risk_events(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(db, session_id, current_user.id)
    return db.scalars(
        select(RiskEvent)
        .where(RiskEvent.session_id == session_id)
        .order_by(RiskEvent.started_at.asc())
    ).all()


@router.get(
    "/sessions/{session_id}/alert-notifications",
    response_model=list[AlertNotificationResponse],
)
def get_session_alert_notifications(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _owned_session(db, session_id, current_user.id)
    return db.scalars(
        select(AlertNotification)
        .where(AlertNotification.session_id == session_id)
        .order_by(AlertNotification.emitted_at.asc())
    ).all()
