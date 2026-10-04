from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

class AlertEventType(str, Enum):
    NECK_FLEXION = "NECK_FLEXION"
    NECK_LATERAL_TILT = "NECK_LATERAL_TILT"
    NECK_ROTATION = "NECK_ROTATION"
    FORWARD_HEAD = "FORWARD_HEAD"
    SHOULDER_TILT = "SHOULDER_TILT"
    SCREEN_DISTANCE = "SCREEN_DISTANCE"
    LOW_BLINK_RATE = "LOW_BLINK_RATE"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class AlertEventCreate(BaseModel):
    event_type: AlertEventType
    risk_level: RiskLevel

class AlertEventResponse(BaseModel):
    event_id: int
    session_id: int
    event_type: str
    risk_level: str
    started_at: datetime
    ended_at: datetime | None
    duration: int

    model_config = ConfigDict(from_attributes=True)