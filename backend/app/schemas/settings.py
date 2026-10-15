from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserSettingsUpdate(BaseModel):
    notifications_enabled: bool
    sound_enabled: bool
    sound_volume: int = Field(ge=0, le=100)
    reminder_interval_minutes: int = Field(ge=1, le=60)


class UserSettingsResponse(UserSettingsUpdate):
    user_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
