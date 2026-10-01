from datetime import datetime

from pydantic import BaseModel, ConfigDict

class SessionStart(BaseModel):
    camera_id: int
    baseline_id: int

class SessionResponse(BaseModel):
    session_id: int
    user_id: int
    baseline_id: int
    camera_id: int

    started_at: datetime
    ended_at: datetime | None
    paused_at: datetime | None

    status: str

    total_duration: int
    paused_duration: int
    pause_count: int

    model_config = ConfigDict(from_attributes=True)