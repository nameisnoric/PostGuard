
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionSummaryCreate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    average_risk_score: float | None = Field(default=None, ge=0, le=3)
    maximum_risk_score: float | None = Field(default=None, ge=0, le=3)
    rula_final_score: int | None = Field(default=None, ge=1, le=7, strict=True)
    rula_action_level: int | None = Field(default=None, ge=1, le=4, strict=True)
    blink_rate: float | None = Field(default=None, ge=0)

    detection_count: int = Field(default=0, ge=0, strict=True)
    pose_detected_count: int = Field(default=0, ge=0, strict=True)
    face_detected_count: int = Field(default=0, ge=0, strict=True)

    average_shoulder: float | None = None
    average_neck: float | None = None

    @model_validator(mode="after")
    def validate_detection_counts(self):
        if max(self.pose_detected_count, self.face_detected_count) > self.detection_count:
            raise ValueError("Detected counts cannot exceed detection_count")
        if (
            self.average_risk_score is not None
            and self.maximum_risk_score is not None
            and self.maximum_risk_score < self.average_risk_score
        ):
            raise ValueError(
                "maximum_risk_score cannot be below average_risk_score"
            )
        if (self.rula_final_score is None) != (self.rula_action_level is None):
            raise ValueError("RULA score and action level must be provided together")
        if self.rula_final_score is not None:
            expected_level = (
                1 if self.rula_final_score <= 2 else
                2 if self.rula_final_score <= 4 else
                3 if self.rula_final_score <= 6 else 4
            )
            if self.rula_action_level != expected_level:
                raise ValueError("RULA action level does not match final score")
        return self


class SessionSummaryResponse(BaseModel):
    summary_id: int
    session_id: int

    average_risk_score: float | None
    maximum_risk_score: float | None
    rula_final_score: int | None
    rula_action_level: int | None

    detection_count: int
    pose_detected_count: int
    face_detected_count: int
    average_shoulder: float | None
    average_neck: float | None

    low_risk_duration: int
    medium_risk_duration: int
    high_risk_duration: int

    low_risk_alert_count: int
    medium_risk_alert_count: int
    high_risk_alert_count: int

    total_alert_count: int
    most_frequent_alert_event: str | None
    blink_rate: float | None

    model_config = ConfigDict(from_attributes=True)
