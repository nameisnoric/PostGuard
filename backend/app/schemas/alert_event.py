from datetime import datetime

from pydantic import BaseModel, ConfigDict

class AlertEventCreate(BaseModel):
    event_type: str
    risk_level: str

class AlertEventResponse(BaseModel):
    event_id: int
    session_id: int
    event_type: str
    risk_level: str
    started_at: datetime
    ended_at: datetime | None
    duration: int

    model_config = ConfigDict(from_attributes=True)