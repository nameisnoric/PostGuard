from datetime import datetime

from pydantic import BaseModel, ConfigDict

class PersonalBaselineCreate(BaseModel):
    camera_id: int

    neck_flexion_baseline: float | None = None
    shoulder_angle: float | None = None
    lateral_tilt_baseline: float | None = None
    shoulder_tilt_status: str | None = None
    forward_head_baseline: float | None = None
    neck_rotation_baseline: float | None = None
    shoulder_level_difference_baseline: float | None = None
    ipd_baseline: float | None = None
    screen_distance_baseline: float | None = None

class PersonalBaselineResponse(BaseModel):
    baseline_id: int
    user_id: int
    camera_id: int

    neck_flexion_baseline: float | None
    shoulder_angle: float | None
    lateral_tilt_baseline: float | None
    shoulder_tilt_status: str | None
    forward_head_baseline: float | None
    neck_rotation_baseline: float | None
    shoulder_level_difference_baseline: float | None
    ipd_baseline: float | None
    screen_distance_baseline: float | None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)