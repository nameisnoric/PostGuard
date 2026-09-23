from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base

class PasswordResetOTP(Base):
    __tablename__ = "password_reset"

    id: Mapped[int] = mapped_column(
        primary_key= True,
        index= True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete=("CASCADE")),
        nullable= False,
        index= True
    )

    otp_hash: Mapped[str] = mapped_column(
        String(255),
        nullable= False
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable= False
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable= True
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default= 0,
        nullable= False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone= True),
        nullable= False
    )

    reset_token_jti: Mapped[str | None] = mapped_column(
        String(50),
        unique= True,
        nullable= True
    )

    reset_token_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone = True),
        nullable= True
    )