from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.database import Base

class Camera(Base):
    __tablename__ = "cameras"

    camera_id: Mapped[int] = mapped_column(
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

    device_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    camera_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    resolution_width: Mapped[int] = mapped_column(
        nullable=False
    )

    resolution_height: Mapped[int] = mapped_column(
        nullable=False
    )

    reprojection_error: Mapped[float | None] = mapped_column(
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False
    )