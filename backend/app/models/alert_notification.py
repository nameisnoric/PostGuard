"""Idempotent user-notification records emitted for a risk event."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class AlertNotification(Base):
    __tablename__ = "alert_notifications"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "runtime_notification_id",
            name="uq_alert_notifications_session_runtime_notification",
        ),
    )

    notification_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    risk_event_id: Mapped[int] = mapped_column(
        ForeignKey("risk_events.risk_event_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable only for rows created by the teammate migration before the
    # idempotency key was introduced. Every new API request requires this key.
    runtime_notification_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(32), nullable=False, default="ALERT")
    reason: Mapped[str | None] = mapped_column(String(128))
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
