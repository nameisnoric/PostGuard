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

    baseline_status: str | None = Field(default=None, max_length=24)
    confirmation_status: str | None = Field(default=None, max_length=24)
    baseline_sample_count: int | None = Field(default=None, ge=2)
    baseline_duration_seconds: float | None = Field(
        default=None, gt=0, allow_inf_nan=False
    )
    baseline_valid_ratio: float | None = Field(
        default=None, ge=0, le=1, allow_inf_nan=False
    )
    shoulder_tilt_sd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    neck_lateral_tilt_sd: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    neck_flexion_sd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    eye_distance_sd: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    neck_flexion_baseline: float | None = Field(default=None, allow_inf_nan=False)
    shoulder_angle: float | None = Field(default=None, allow_inf_nan=False)
    lateral_tilt_baseline: float | None = Field(default=None, allow_inf_nan=False)
    shoulder_tilt_status: str | None = None
    forward_head_baseline: float | None = None
    neck_rotation_baseline: float | None = None
    shoulder_level_difference_baseline: float | None = None
    ipd_baseline: float | None = Field(default=None, gt=0, allow_inf_nan=False)
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

    baseline_status: str | None
    confirmation_status: str | None
    baseline_sample_count: int | None
    baseline_duration_seconds: float | None
    baseline_valid_ratio: float | None
    shoulder_tilt_sd: float | None
    neck_lateral_tilt_sd: float | None
    neck_flexion_sd: float | None
    eye_distance_sd: float | None

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
