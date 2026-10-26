"""Shared lifecycle helpers for persisted risk events."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk_event import RiskEvent


RISK_RANK = {"MODERATE": 1, "HIGH": 2}


def elapsed_seconds(started_at: datetime, ended_at: datetime) -> float:
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=timezone.utc)
    return max(0.0, (ended_at - started_at).total_seconds())


def update_max_level(event: RiskEvent, level: str) -> None:
    if RISK_RANK.get(level, 0) > RISK_RANK.get(event.max_risk_level, 0):
        event.max_risk_level = level


def close_active_risk_events(
    db: Session,
    session_id: int,
    *,
    reason: str,
    ended_at: datetime | None,
) -> None:
    events = db.scalars(
        select(RiskEvent).where(
            RiskEvent.session_id == session_id,
            RiskEvent.status == "ACTIVE",
        )
    ).all()
    for event in events:
        if ended_at is None:
            event.status = "INCOMPLETE"
            event.resolved_reason = reason
            continue
        event.status = "RESOLVED"
        event.ended_at = ended_at
        event.duration_seconds = elapsed_seconds(event.started_at, ended_at)
        event.resolved_reason = reason
