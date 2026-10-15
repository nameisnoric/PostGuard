"""Permanent cleanup for accounts whose 14-day recovery period has ended."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.register_otp import RegistrationOTP
from app.models.user import User
from app.services.avatar_storage import AvatarStorageError, SupabaseAvatarStorage


def purge_due_accounts(
    db: Session,
    storage: SupabaseAvatarStorage,
    now: datetime | None = None,
) -> dict[str, list]:
    """Delete due accounts and return IDs purged or deferred for storage retry."""
    cutoff = now or datetime.now(timezone.utc)
    users = db.scalars(
        select(User).where(
            User.account_status == "PENDING_DELETION",
            User.deletion_scheduled_for.is_not(None),
            User.deletion_scheduled_for <= cutoff,
        ).with_for_update(skip_locked=True)
    ).all()
    purged_ids: list[int] = []
    deferred_ids: list[int] = []

    for user in users:
        if user.avatar_path:
            try:
                storage.delete(user.avatar_path)
            except AvatarStorageError:
                deferred_ids.append(user.id)
                continue
        db.execute(delete(RegistrationOTP).where(RegistrationOTP.email == user.email))
        user_id = user.id
        db.delete(user)
        db.commit()
        purged_ids.append(user_id)

    return {"purged_ids": purged_ids, "deferred_ids": deferred_ids}
