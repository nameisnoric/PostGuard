from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

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

    total_duration: int | None
    paused_duration: int | None
    pause_count: int

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def hide_unknown_interrupted_duration(self):
        if self.status == "INTERRUPTED":
            self.total_duration = None
            self.paused_duration = None
        return self
