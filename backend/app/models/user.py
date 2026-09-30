from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base

# โครงสร้างส่วน users SQLAlchemy

class User(Base):
    __tablename__ = "users"
#PK 
    id: Mapped[int] = mapped_column(
        primary_key = True,
        index = True
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique = True,
        index = True,
        nullable = False
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique = True,
        index = True,
        nullable = False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable = False
    )

    full_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable = True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    