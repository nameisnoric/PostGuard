from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.database import Base

class PersonalBaseline(Base):
    __tablename__ = "personal_baselines"

    baseline_id: Mapped[int] = mapped_column(
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

    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.camera_id"),
        nullable=False,
        index=True
    )

    neck_flexion_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    shoulder_angle: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    lateral_tilt_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    shoulder_tilt_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    forward_head_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    neck_rotation_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    shoulder_level_difference_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    ipd_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    screen_distance_baseline: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )