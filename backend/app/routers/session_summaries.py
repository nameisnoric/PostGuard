from collections import Counter

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.alert_notification import AlertNotification
from app.models.risk_event_record import RiskEventRecord
from app.models.session import PostureSession
from app.models.session_summary import SessionSummary
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.session_summary import (
    SessionSummaryCreate,
    SessionSummaryResponse,
)


router = APIRouter(
    tags=["Session Summaries"]
)


# ============================================================
# HELPERS
# ============================================================

def _safe_duration(
    value,
) -> float:
    """
    Convert a persisted duration to a safe non-negative value.
    """

    if type(value) not in (
        int,
        float,
    ):
        return 0.0

    return max(
        0.0,
        float(value),
    )


def _risk_event_duration(
    event: RiskEventRecord,
) -> float:
    """
    Return the persisted duration of one Risk Event.
    """

    return _safe_duration(
        event.duration_seconds
    )


def _summary_request_values(
    request: SessionSummaryCreate,
) -> dict:
    """
    Preserve every Session Summary field currently supported
    by SessionSummaryCreate, but only if the database model
    actually has that column.

    This is important because PostGuard already persists
    Detection Summary fields such as:

    - detection_count
    - pose_detected_count
    - face_detected_count
    - average_shoulder
    - average_neck

    We must not lose those fields while migrating AlertEvent
    to RiskEventRecord + AlertNotification.
    """

    request_data = request.model_dump()

    database_columns = {
        column.name
        for column
        in SessionSummary.__table__.columns
    }

    protected_fields = {
        "summary_id",
        "session_id",
        "low_risk_duration",
        "medium_risk_duration",
        "high_risk_duration",
        "low_risk_alert_count",
        "medium_risk_alert_count",
        "high_risk_alert_count",
        "total_alert_count",
        "most_frequent_alert_event",
    }

    return {
        key: value
        for key, value
        in request_data.items()
        if (
            key in database_columns
            and
            key not in protected_fields
        )
    }


# ============================================================
# CREATE SESSION SUMMARY
# ============================================================

@router.post(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session_summary(
    session_id: int,
    request: SessionSummaryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    # --------------------------------------------------------
    # 1. Verify Session ownership
    # --------------------------------------------------------

    session_statement = (
        select(PostureSession)
        .where(
            PostureSession.session_id
            == session_id,

            PostureSession.user_id
            == current_user.id,
        )
    )

    posture_session = db.scalar(
        session_statement
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    # --------------------------------------------------------
    # 2. Only completed Session can have final Summary
    # --------------------------------------------------------

    if (
        posture_session.status
        != "COMPLETED"
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Session must be completed "
                "before creating a summary"
            ),
        )

    # --------------------------------------------------------
    # 3. Prevent duplicate Summary
    # --------------------------------------------------------

    existing_statement = (
        select(SessionSummary)
        .where(
            SessionSummary.session_id
            == session_id
        )
    )

    existing_summary = db.scalar(
        existing_statement
    )

    if existing_summary is not None:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Session summary already exists"
            ),
        )

    # --------------------------------------------------------
    # 4. Load persisted Risk Events
    # --------------------------------------------------------

    risk_event_statement = (
        select(RiskEventRecord)
        .where(
            RiskEventRecord.session_id
            == session_id
        )
        .order_by(
            RiskEventRecord.started_at.asc()
        )
    )

    risk_events = list(
        db.scalars(
            risk_event_statement
        ).all()
    )

    # --------------------------------------------------------
    # 5. Load persisted Alert Notifications
    # --------------------------------------------------------

    notification_statement = (
        select(AlertNotification)
        .where(
            AlertNotification.session_id
            == session_id
        )
        .order_by(
            AlertNotification.emitted_at.asc()
        )
    )

    notifications = list(
        db.scalars(
            notification_statement
        ).all()
    )

    # --------------------------------------------------------
    # 6. Risk Event duration
    #
    # Existing DB schema still uses "medium",
    # but the validated Risk Pipeline calls it MODERATE.
    #
    # medium_risk_* therefore currently means MODERATE.
    # --------------------------------------------------------

    low_risk_duration = sum(
        _risk_event_duration(
            event
        )
        for event
        in risk_events
        if (
            event.current_risk_level
            == "LOW"
        )
    )

    medium_risk_duration = sum(
        _risk_event_duration(
            event
        )
        for event
        in risk_events
        if (
            event.current_risk_level
            == "MODERATE"
        )
    )

    high_risk_duration = sum(
        _risk_event_duration(
            event
        )
        for event
        in risk_events
        if (
            event.current_risk_level
            == "HIGH"
        )
    )

    # --------------------------------------------------------
    # 7. Notification count by risk level
    #
    # Important:
    # These are notifications, NOT risk episodes.
    # --------------------------------------------------------

    low_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            == "LOW"
        )
    )

    medium_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            == "MODERATE"
        )
    )

    high_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            == "HIGH"
        )
    )

    total_alert_count = len(
        notifications
    )

    # --------------------------------------------------------
    # 8. Most frequent notification type
    #
    # FIRST / REPEAT / ESCALATION
    # --------------------------------------------------------

    most_frequent_alert_event = None

    if notifications:
        counter = Counter(
            notification.alert_type
            for notification
            in notifications
        )

        most_frequent_alert_event = (
            counter.most_common(
                1
            )[0][0]
        )

    # --------------------------------------------------------
    # 9. Preserve existing Detection Summary fields
    #
    # This fixes the regression where detection_count became 0.
    # --------------------------------------------------------

    summary_values = (
        _summary_request_values(
            request
        )
    )

    # --------------------------------------------------------
    # 10. Create final Session Summary
    # --------------------------------------------------------

    session_summary = SessionSummary(
        session_id=session_id,

        **summary_values,

        low_risk_duration=int(
            round(
                low_risk_duration
            )
        ),

        medium_risk_duration=int(
            round(
                medium_risk_duration
            )
        ),

        high_risk_duration=int(
            round(
                high_risk_duration
            )
        ),

        low_risk_alert_count=(
            low_risk_alert_count
        ),

        medium_risk_alert_count=(
            medium_risk_alert_count
        ),

        high_risk_alert_count=(
            high_risk_alert_count
        ),

        total_alert_count=(
            total_alert_count
        ),

        most_frequent_alert_event=(
            most_frequent_alert_event
        ),
    )

    db.add(
        session_summary
    )

    db.commit()

    db.refresh(
        session_summary
    )

    return session_summary


# ============================================================
# GET ONE SESSION SUMMARY
# ============================================================

@router.get(
    "/sessions/{session_id}/summary",
    response_model=SessionSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def get_session_summary(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    session_statement = (
        select(PostureSession)
        .where(
            PostureSession.session_id
            == session_id,

            PostureSession.user_id
            == current_user.id,
        )
    )

    posture_session = db.scalar(
        session_statement
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    summary_statement = (
        select(SessionSummary)
        .where(
            SessionSummary.session_id
            == session_id
        )
    )

    session_summary = db.scalar(
        summary_statement
    )

    if session_summary is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Session summary not found"
            ),
        )

    return session_summary


# ============================================================
# GET ALL SUMMARIES
# ============================================================

@router.get(
    "/summaries",
    response_model=list[
        SessionSummaryResponse
    ],
    status_code=status.HTTP_200_OK,
)
def get_summaries(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    statement = (
        select(SessionSummary)
        .join(
            PostureSession,
            (
                SessionSummary.session_id
                ==
                PostureSession.session_id
            ),
        )
        .where(
            PostureSession.user_id
            == current_user.id
        )
        .order_by(
            PostureSession.started_at.desc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )