from __future__ import annotations

from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.models.alert_notification import (
    AlertNotification,
)
from app.models.risk_event_record import (
    RiskEventRecord,
)
from app.models.session import (
    PostureSession,
)
from app.models.user import User

from app.routers.auth import (
    get_current_user,
)

from app.schemas.risk_persistence import (
    AlertNotificationCreate,
    AlertNotificationResponse,
    RiskEventResolve,
    RiskEventResponse,
    RiskEventStart,
    RiskEventUpdate,
)


router = APIRouter(
    tags=[
        "Risk Persistence",
    ]
)


RISK_ORDER = {
    "MODERATE": 1,
    "HIGH": 2,
}


# ============================================================
# Helpers
# ============================================================

def _get_user_session(
    *,
    session_id: int,
    db: Session,
    current_user: User,
) -> PostureSession:

    statement = select(
        PostureSession
    ).where(
        PostureSession.session_id
        ==
        session_id,

        PostureSession.user_id
        ==
        current_user.id,
    )

    posture_session = db.scalar(
        statement
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    return posture_session


def _get_risk_event(
    *,
    session_id: int,
    runtime_event_id: str,
    db: Session,
) -> RiskEventRecord:

    statement = select(
        RiskEventRecord
    ).where(
        RiskEventRecord.session_id
        ==
        session_id,

        RiskEventRecord.runtime_event_id
        ==
        runtime_event_id,
    )

    risk_event = db.scalar(
        statement
    )

    if risk_event is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Risk event not found",
        )

    return risk_event


def _elapsed_seconds(
    started_at: datetime,
    now: datetime,
) -> float:

    duration = (
        now
        -
        started_at
    ).total_seconds()

    return max(
        0.0,
        float(duration),
    )


def _higher_risk(
    left: str,
    right: str,
) -> str:

    left_rank = RISK_ORDER.get(
        left,
        0,
    )

    right_rank = RISK_ORDER.get(
        right,
        0,
    )

    if right_rank > left_rank:
        return right

    return left


# ============================================================
# START
# ============================================================

@router.post(
    "/sessions/{session_id}/risk-events",
    response_model=RiskEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_risk_event(
    session_id: int,
    request: RiskEventStart,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Persist RiskEventTracker STARTED.

    Safe retry behavior:
    If this runtime_event_id already exists for the Session,
    return the existing row instead of duplicating it.
    """

    posture_session = (
        _get_user_session(
            session_id=session_id,
            db=db,
            current_user=current_user,
        )
    )

    if posture_session.status != "RUNNING":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Risk events can only start "
                "while the session is RUNNING"
            ),
        )

    existing_statement = select(
        RiskEventRecord
    ).where(
        RiskEventRecord.session_id
        ==
        session_id,

        RiskEventRecord.runtime_event_id
        ==
        request.runtime_event_id,
    )

    existing = db.scalar(
        existing_statement
    )

    if existing is not None:
        return existing

    now = datetime.now(
        timezone.utc
    )

    risk_event = RiskEventRecord(
        session_id=session_id,

        runtime_event_id=(
            request.runtime_event_id
        ),

        initial_risk_level=(
            request.risk_level
        ),

        current_risk_level=(
            request.risk_level
        ),

        max_risk_level=(
            request.risk_level
        ),

        status="ACTIVE",

        started_at=now,

        ended_at=None,

        duration_seconds=0.0,

        resolved_reason=None,

        active_factors=(
            list(
                request.active_factors
            )
        ),

        evidence_groups=(
            list(
                request.evidence_groups
            )
        ),
    )

    db.add(
        risk_event
    )

    db.commit()

    db.refresh(
        risk_event
    )

    return risk_event


# ============================================================
# UPDATE / ESCALATE / DEESCALATE / DATA GAP
# ============================================================

@router.patch(
    "/sessions/{session_id}/risk-events/{runtime_event_id}",
    response_model=RiskEventResponse,
    status_code=status.HTTP_200_OK,
)
def update_risk_event(
    session_id: int,
    runtime_event_id: str,
    request: RiskEventUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    posture_session = (
        _get_user_session(
            session_id=session_id,
            db=db,
            current_user=current_user,
        )
    )

    if posture_session.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Cannot update a risk event "
                "for an inactive session"
            ),
        )

    risk_event = (
        _get_risk_event(
            session_id=session_id,
            runtime_event_id=(
                runtime_event_id
            ),
            db=db,
        )
    )

    if risk_event.status != "ACTIVE":
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail="Risk event is already resolved",
        )

    if request.event_action == "RESOLVED":
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Use the resolve endpoint "
                "for RESOLVED events"
            ),
        )

    now = datetime.now(
        timezone.utc
    )

    risk_event.current_risk_level = (
        request.risk_level
    )

    risk_event.max_risk_level = (
        _higher_risk(
            risk_event.max_risk_level,
            request.risk_level,
        )
    )

    risk_event.duration_seconds = (
        _elapsed_seconds(
            risk_event.started_at,
            now,
        )
    )

    risk_event.active_factors = (
        list(
            request.active_factors
        )
    )

    risk_event.evidence_groups = (
        list(
            request.evidence_groups
        )
    )

    risk_event.updated_at = now

    db.commit()

    db.refresh(
        risk_event
    )

    return risk_event


# ============================================================
# RESOLVE
# ============================================================

@router.post(
    "/sessions/{session_id}/risk-events/{runtime_event_id}/resolve",
    response_model=RiskEventResponse,
    status_code=status.HTTP_200_OK,
)
def resolve_risk_event(
    session_id: int,
    runtime_event_id: str,
    request: RiskEventResolve,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    _get_user_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    risk_event = (
        _get_risk_event(
            session_id=session_id,
            runtime_event_id=(
                runtime_event_id
            ),
            db=db,
        )
    )

    # Safe retry.
    if risk_event.status == "RESOLVED":
        return risk_event

    now = datetime.now(
        timezone.utc
    )

    risk_event.status = (
        "RESOLVED"
    )

    risk_event.ended_at = now

    risk_event.duration_seconds = (
        _elapsed_seconds(
            risk_event.started_at,
            now,
        )
    )

    risk_event.resolved_reason = (
        request.resolved_reason
    )

    risk_event.updated_at = now

    db.commit()

    db.refresh(
        risk_event
    )

    return risk_event


# ============================================================
# NOTIFICATION
# ============================================================

@router.post(
    (
        "/sessions/{session_id}"
        "/risk-events/{runtime_event_id}"
        "/notifications"
    ),
    response_model=(
        AlertNotificationResponse
    ),
    status_code=status.HTTP_201_CREATED,
)
def create_alert_notification(
    session_id: int,
    runtime_event_id: str,
    request: AlertNotificationCreate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    posture_session = (
        _get_user_session(
            session_id=session_id,
            db=db,
            current_user=current_user,
        )
    )

    if posture_session.status not in (
        "RUNNING",
        "PAUSED",
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Cannot create a notification "
                "for an inactive session"
            ),
        )

    risk_event = (
        _get_risk_event(
            session_id=session_id,
            runtime_event_id=(
                runtime_event_id
            ),
            db=db,
        )
    )

    notification = AlertNotification(
        risk_event_id=(
            risk_event.risk_event_id
        ),

        session_id=session_id,

        alert_type=(
            request.alert_type
        ),

        risk_level=(
            request.risk_level
        ),

        decision=(
            request.decision
        ),

        reason=(
            request.reason
        ),

        emitted_at=(
            datetime.now(
                timezone.utc
            )
        ),
    )

    db.add(
        notification
    )

    db.commit()

    db.refresh(
        notification
    )

    return notification


# ============================================================
# LIST SESSION RISK EVENTS
# ============================================================

@router.get(
    "/sessions/{session_id}/risk-events",
    response_model=list[
        RiskEventResponse
    ],
    status_code=status.HTTP_200_OK,
)
def get_session_risk_events(
    session_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    _get_user_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    statement = (
        select(
            RiskEventRecord
        )
        .where(
            RiskEventRecord.session_id
            ==
            session_id
        )
        .order_by(
            RiskEventRecord.started_at.asc()
        )
    )

    return (
        db.scalars(
            statement
        )
        .all()
    )


# ============================================================
# LIST SESSION NOTIFICATIONS
# ============================================================

@router.get(
    "/sessions/{session_id}/alert-notifications",
    response_model=list[
        AlertNotificationResponse
    ],
    status_code=status.HTTP_200_OK,
)
def get_session_alert_notifications(
    session_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    _get_user_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    statement = (
        select(
            AlertNotification
        )
        .where(
            AlertNotification.session_id
            ==
            session_id
        )
        .order_by(
            AlertNotification.emitted_at.asc()
        )
    )

    return (
        db.scalars(
            statement
        )
        .all()
    )