from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class AlertNotification(Base):
    """
    Persistent notification emitted by Alert Policy.

    Examples:
    - FIRST
    - REPEAT
    - ESCALATION

    Important:
    One Risk Event can produce multiple Alert Notifications.
    """

    __tablename__ = "alert_notifications"

    notification_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    risk_event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "risk_events.risk_event_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "sessions.session_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    risk_level: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ALERT",
    )

    reason: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(
            timezone.utc
        ),
    )