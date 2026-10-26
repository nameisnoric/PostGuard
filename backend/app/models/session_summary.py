from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.database import Base


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    summary_id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sessions.session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    # ========================================================
    # POSTGUARD RISK SCORE
    #
    # Presentation score:
    # 0 - 100
    #
    # None means there were no COMPLETE posture-score samples
    # available for this Session.
    # ========================================================

    # ========================================================
    # POSTGUARD RISK SCORE
    # ========================================================

    average_risk_score: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    minimum_risk_score: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    maximum_risk_score: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    risk_score_method: Mapped[
        str | None
    ] = mapped_column(
        String(40),
        nullable=True,
    )

    # ========================================================
    # DETECTION SUMMARY
    # ========================================================

    detection_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    pose_detected_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    face_detected_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    average_shoulder: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    average_neck: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    # ========================================================
    # RISK EVENT DURATION
    #
    # Existing schema uses "medium".
    # Validated pipeline calls this MODERATE.
    # ========================================================

    low_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    medium_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    high_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # ========================================================
    # ALERT NOTIFICATION COUNTS
    # ========================================================

    low_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    medium_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    high_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    most_frequent_alert_event: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    # ========================================================
    # FUTURE BLINK SUMMARY
    # ========================================================

    blink_rate: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )