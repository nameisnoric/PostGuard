from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EyeAlertNotificationCreate(BaseModel):
    runtime_notification_id: str = Field(min_length=1, max_length=128)
    alert_type: Literal["FIRST", "REPEAT"]
    blink_rate: float = Field(ge=0.0)
    window_blink_count: int = Field(ge=0, strict=True)
    decision: str = Field(default="ALERT", min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=128)


class EyeAlertNotificationResponse(BaseModel):
    eye_notification_id: int
    session_id: int
    runtime_notification_id: str
    alert_type: str
    blink_rate: float
    window_blink_count: int
    decision: str
    reason: str | None
    emitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
