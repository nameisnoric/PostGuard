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

from app.models.alert_notification import (
    AlertNotification,
)
from app.models.risk_event_record import (
    RiskEventRecord,
)
from app.models.session import (
    PostureSession,
)
from app.models.session_summary import (
    SessionSummary,
)
from app.models.session_risk_score_bucket import (
    SessionRiskScoreBucket,
)
from app.models.user import User

from app.routers.auth import (
    get_current_user,
)

from app.schemas.session_summary import (
    SessionRiskScoreBucketResponse,
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
    return _safe_duration(
        event.duration_seconds
    )


def _get_owned_session(
    *,
    db: Session,
    session_id: int,
    user_id: int,
) -> PostureSession | None:
    statement = (
        select(
            PostureSession
        )
        .where(
            PostureSession.session_id
            ==
            session_id,

            PostureSession.user_id
            ==
            user_id,
        )
    )

    return db.scalar(
        statement
    )


def _summary_request_values(
    request: SessionSummaryCreate,
) -> dict:
    """
    Persist only fields that belong to SessionSummary.

    risk_score_buckets is intentionally excluded because
    those records belong to a separate table.
    """

    request_data = (
        request.model_dump(
            exclude={
                "risk_score_buckets"
            }
        )
    )

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
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    # --------------------------------------------------------
    # 1. Session ownership
    # --------------------------------------------------------

    posture_session = (
        _get_owned_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
        )
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    # --------------------------------------------------------
    # 2. Final Summary only for completed Session
    # --------------------------------------------------------

    if (
        posture_session.status
        !=
        "COMPLETED"
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
    # 3. No duplicate Summary
    # --------------------------------------------------------

    existing_summary = db.scalar(
        select(
            SessionSummary
        )
        .where(
            SessionSummary.session_id
            ==
            session_id
        )
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
    # 4. Load Risk Events
    # --------------------------------------------------------

    risk_events = list(
        db.scalars(
            select(
                RiskEventRecord
            )
            .where(
                RiskEventRecord.session_id
                ==
                session_id
            )
            .order_by(
                RiskEventRecord
                .started_at
                .asc()
            )
        ).all()
    )

    # --------------------------------------------------------
    # 5. Load Alert Notifications
    # --------------------------------------------------------

    notifications = list(
        db.scalars(
            select(
                AlertNotification
            )
            .where(
                AlertNotification.session_id
                ==
                session_id
            )
            .order_by(
                AlertNotification
                .emitted_at
                .asc()
            )
        ).all()
    )

    # --------------------------------------------------------
    # 6. Risk Event durations
    # --------------------------------------------------------

    low_risk_duration = sum(
        _risk_event_duration(
            event
        )
        for event
        in risk_events
        if (
            event.current_risk_level
            ==
            "LOW"
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
            ==
            "MODERATE"
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
            ==
            "HIGH"
        )
    )

    # --------------------------------------------------------
    # 7. Notification counts
    # --------------------------------------------------------

    low_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            ==
            "LOW"
        )
    )

    medium_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            ==
            "MODERATE"
        )
    )

    high_risk_alert_count = sum(
        1
        for notification
        in notifications
        if (
            notification.risk_level
            ==
            "HIGH"
        )
    )

    total_alert_count = len(
        notifications
    )

    # --------------------------------------------------------
    # 8. Most frequent notification type
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
    # 9. User-provided measured values
    # --------------------------------------------------------

    summary_values = (
        _summary_request_values(
            request
        )
    )

    # --------------------------------------------------------
    # 10. Build Summary
    # --------------------------------------------------------

    session_summary = (
        SessionSummary(
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
    )

    db.add(
        session_summary
    )

    # --------------------------------------------------------
    # 11. Persist graph buckets
    #
    # Do not trust client-side session_id.
    # session_id always comes from URL.
    # --------------------------------------------------------

    for bucket in (
        request.risk_score_buckets
    ):
        db.add(
            SessionRiskScoreBucket(
                session_id=session_id,

                bucket_index=(
                    bucket.bucket_index
                ),

                start_second=(
                    bucket.start_second
                ),

                end_second=(
                    bucket.end_second
                ),

                sample_count=(
                    bucket.sample_count
                ),

                average_risk_score=(
                    bucket.average_risk_score
                ),

                minimum_risk_score=(
                    bucket.minimum_risk_score
                ),

                maximum_risk_score=(
                    bucket.maximum_risk_score
                ),

                minimum_modified_rula_score=(
                    bucket
                    .minimum_modified_rula_score
                ),

                maximum_modified_rula_score=(
                    bucket
                    .maximum_modified_rula_score
                ),
            )
        )

    # --------------------------------------------------------
    # 12. One atomic transaction
    # --------------------------------------------------------

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

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
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    posture_session = (
        _get_owned_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
        )
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    session_summary = db.scalar(
        select(
            SessionSummary
        )
        .where(
            SessionSummary.session_id
            ==
            session_id
        )
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
# GET SESSION RISK SCORE BUCKETS
# ============================================================

@router.get(
    (
        "/sessions/{session_id}"
        "/risk-score-buckets"
    ),
    response_model=list[
        SessionRiskScoreBucketResponse
    ],
    status_code=status.HTTP_200_OK,
)
def get_session_risk_score_buckets(
    session_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    posture_session = (
        _get_owned_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
        )
    )

    if posture_session is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Session not found",
        )

    statement = (
        select(
            SessionRiskScoreBucket
        )
        .where(
            SessionRiskScoreBucket.session_id
            ==
            session_id
        )
        .order_by(
            SessionRiskScoreBucket
            .bucket_index
            .asc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


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
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    statement = (
        select(
            SessionSummary
        )
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
            ==
            current_user.id
        )
        .order_by(
            PostureSession
            .started_at
            .desc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )