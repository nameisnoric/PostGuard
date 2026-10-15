from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class PersonalBaselineCreate(BaseModel):
    camera_id: int

    camera_frame_width: int | None = Field(default=None, gt=0)
    camera_frame_height: int | None = Field(default=None, gt=0)
    camera_scale_x: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    camera_scale_y: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    camera_scale_avg: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    camera_card_roll: float | None = Field(default=None, allow_inf_nan=False)
    camera_horizontal_perspective: float | None = Field(
        default=None, ge=0, le=1, allow_inf_nan=False
    )
    camera_vertical_perspective: float | None = Field(
        default=None, ge=0, le=1, allow_inf_nan=False
    )
    camera_calibrated_at: datetime | None = None

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

    camera_frame_width: int | None
    camera_frame_height: int | None
    camera_scale_x: float | None
    camera_scale_y: float | None
    camera_scale_avg: float | None
    camera_card_roll: float | None
    camera_horizontal_perspective: float | None
    camera_vertical_perspective: float | None
    camera_calibrated_at: datetime | None

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
