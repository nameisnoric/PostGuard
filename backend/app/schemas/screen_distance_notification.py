from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScreenDistanceNotificationCreate(BaseModel):
    runtime_notification_id: str = Field(min_length=1, max_length=128)
    alert_type: Literal["FIRST", "REPEAT"]
    distance_ratio: float = Field(gt=0.0)
    decision: str = Field(default="ALERT", min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=128)


class ScreenDistanceNotificationResponse(BaseModel):
    screen_notification_id: int
    session_id: int
    runtime_notification_id: str
    alert_type: str
    distance_ratio: float
    decision: str
    reason: str | None
    emitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
