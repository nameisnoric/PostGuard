from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database.database import Base


class EyeAlertNotification(Base):
    # Persisted FIRST/REPEAT Eye Reminder, separate from posture Risk Events.

    __tablename__ = "eye_alert_notifications"

    eye_notification_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    blink_rate: Mapped[float] = mapped_column(Float, nullable=False)
    window_blink_count: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="ALERT")
    reason: Mapped[str | None] = mapped_column(String(128), nullable=True)

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
