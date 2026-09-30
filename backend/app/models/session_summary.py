from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base

class SessionSummary(Base):
    __tablename__ = "session_summaries"

    summary_id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sessions.session_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        unique=True,
        index=True
    )

    average_risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )

    maximum_risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )

    low_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    medium_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    high_risk_duration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    low_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    medium_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    high_risk_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_alert_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    most_frequent_alert_event: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    blink_rate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )