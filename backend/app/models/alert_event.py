from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base

class AlertEvent(Base):
    __tablename__ = "alert_events"

    event_id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sessions.session_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        nullable=False
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )

    duration: Mapped[int] = mapped_column(
        nullable=False,
        default=0
    )