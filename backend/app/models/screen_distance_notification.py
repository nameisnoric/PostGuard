"""Persisted FIRST/REPEAT screen-distance reminders shown to the user."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ScreenDistanceNotification(Base):
    __tablename__ = "screen_distance_notifications"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "runtime_notification_id",
            name="uq_screen_distance_session_runtime_notification",
        ),
    )

    screen_notification_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_notification_id: Mapped[str] = mapped_column(String(128), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    distance_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="ALERT")
    reason: Mapped[str | None] = mapped_column(String(128))
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
