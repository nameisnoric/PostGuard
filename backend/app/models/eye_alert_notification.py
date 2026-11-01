"""Persisted FIRST/REPEAT low-blink reminders shown by the desktop app."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class EyeAlertNotification(Base):
    __tablename__ = "eye_alert_notifications"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "runtime_notification_id",
            name="uq_eye_alert_session_runtime_notification",
        ),
    )

    eye_notification_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    runtime_notification_id: Mapped[str] = mapped_column(String(128), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    blink_rate: Mapped[float] = mapped_column(Float, nullable=False)
    window_blink_count: Mapped[int] = mapped_column(Integer, nullable=False)
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
