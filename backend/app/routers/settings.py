from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.routers.auth import get_current_user
from app.schemas.settings import UserSettingsResponse, UserSettingsUpdate


router = APIRouter(prefix="/users/me/settings", tags=["Settings"])


def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    settings = db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_model=UserSettingsResponse)
def read_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_or_create_settings(db, current_user.id)


@router.put("", response_model=UserSettingsResponse, status_code=status.HTTP_200_OK)
def update_settings(
    request: UserSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_or_create_settings(db, current_user.id)
    settings.notifications_enabled = request.notifications_enabled
    settings.sound_enabled = request.sound_enabled
    settings.sound_volume = request.sound_volume
    settings.reminder_interval_minutes = request.reminder_interval_minutes
    db.commit()
    db.refresh(settings)
    return settings
