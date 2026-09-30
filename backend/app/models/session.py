from datetime import datetime

from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.database import Base

class PostureSession(Base):
    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    baseline_id: Mapped[int] = mapped_column(
        ForeignKey("personal_baselines.baseline_id"),
        nullable=False,
        index=True
    )

    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.camera_id"),
        nullable=False,
        index=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="RUNNING"
    )

    total_duration: Mapped[int] = mapped_column(
        nullable=False,
        default=0
    )

    paused_duration: Mapped[int] = mapped_column(
        nullable=False,
        default=0
    )

    pause_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0
    )