from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
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

    # Numeric camera-preparation snapshot captured locally before this baseline.
    # Frames and reference-card images are never persisted.
    camera_frame_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    camera_frame_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    camera_scale_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    camera_scale_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    camera_scale_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    camera_card_roll: Mapped[float | None] = mapped_column(Float, nullable=True)
    camera_horizontal_perspective: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    camera_vertical_perspective: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    camera_calibrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    baseline_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    confirmation_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    baseline_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_valid_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    shoulder_tilt_sd: Mapped[float | None] = mapped_column(Float, nullable=True)
    neck_lateral_tilt_sd: Mapped[float | None] = mapped_column(Float, nullable=True)
    neck_flexion_sd: Mapped[float | None] = mapped_column(Float, nullable=True)
    eye_distance_sd: Mapped[float | None] = mapped_column(Float, nullable=True)

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

    eye_distance_baseline_px: Mapped[float | None] = mapped_column(
    Float,
    nullable=True,
    )
