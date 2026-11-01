from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


# ============================================================
# RISK SCORE BUCKET
# ============================================================

class SessionRiskScoreBucketCreate(
    BaseModel
):
    model_config = ConfigDict(
        allow_inf_nan=False
    )

    bucket_index: int = Field(
        ge=0,
        strict=True,
    )

    start_second: float = Field(
        ge=0.0,
    )

    end_second: float

    sample_count: int = Field(
        ge=1,
        strict=True,
    )

    average_risk_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    minimum_risk_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    maximum_risk_score: float = Field(
        ge=0.0,
        le=100.0,
    )

    minimum_modified_rula_score: (
        int
    ) = Field(
        ge=1,
        le=7,
        strict=True,
    )

    maximum_modified_rula_score: (
        int
    ) = Field(
        ge=1,
        le=7,
        strict=True,
    )

    @model_validator(
        mode="after"
    )
    def validate_bucket(
        self,
    ):
        if (
            self.end_second
            <=
            self.start_second
        ):
            raise ValueError(
                "end_second must be greater "
                "than start_second"
            )

        if not (
            self.minimum_risk_score
            <=
            self.average_risk_score
            <=
            self.maximum_risk_score
        ):
            raise ValueError(
                "Risk scores must satisfy "
                "minimum <= average <= maximum"
            )

        if (
            self.minimum_modified_rula_score
            >
            self.maximum_modified_rula_score
        ):
            raise ValueError(
                "Modified RULA scores must "
                "satisfy minimum <= maximum"
            )

        return self


class SessionRiskScoreBucketResponse(
    SessionRiskScoreBucketCreate
):
    bucket_id: int
    session_id: int

    model_config = ConfigDict(
        from_attributes=True,
        allow_inf_nan=False,
    )


# ============================================================
# SESSION SUMMARY CREATE
# ============================================================

class SessionSummaryCreate(
    BaseModel
):
    model_config = ConfigDict(
        allow_inf_nan=False
    )

    # ========================================================
    # POSTGUARD RISK SCORE
    # ========================================================

    average_risk_score: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        le=100.0,
    )

    minimum_risk_score: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        le=100.0,
    )

    maximum_risk_score: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        le=100.0,
    )

    risk_score_method: (
        str | None
    ) = Field(
        default=None,
        max_length=40,
    )

    risk_score_buckets: list[
        SessionRiskScoreBucketCreate
    ] = Field(
        default_factory=list
    )

    # ========================================================
    # BLINK SUMMARY
    # ========================================================

    blink_rate: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    # ========================================================
    # CAMERA / DATA GAP SUMMARY
    # ========================================================

    data_gap_duration: float = Field(
        default=0.0,
        ge=0.0,
    )

    camera_loss_count: int = Field(
        default=0,
        ge=0,
        strict=True,
    )

    # ========================================================
    # DETECTION SUMMARY
    # ========================================================

    detection_count: int = Field(
        default=0,
        ge=0,
        strict=True,
    )

    pose_detected_count: int = Field(
        default=0,
        ge=0,
        strict=True,
    )

    face_detected_count: int = Field(
        default=0,
        ge=0,
        strict=True,
    )

    average_shoulder: (
        float | None
    ) = None

    average_neck: (
        float | None
    ) = None

    # ========================================================
    # VALIDATION
    # ========================================================

    @model_validator(
        mode="after"
    )
    def validate_summary(
        self,
    ):
        # ----------------------------------------------------
        # Detection count contract
        # ----------------------------------------------------

        if (
            max(
                self.pose_detected_count,
                self.face_detected_count,
            )
            >
            self.detection_count
        ):
            raise ValueError(
                "Detected counts cannot exceed "
                "detection_count"
            )

        # ----------------------------------------------------
        # Risk score availability contract
        #
        # Either all AVG/MIN/MAX are available,
        # or none are available.
        # ----------------------------------------------------

        risk_values = (
            self.average_risk_score,
            self.minimum_risk_score,
            self.maximum_risk_score,
        )

        available_count = sum(
            value is not None
            for value
            in risk_values
        )

        if available_count not in (
            0,
            3,
        ):
            raise ValueError(
                "average/minimum/maximum risk "
                "scores must be provided together"
            )

        if available_count == 3:
            if not (
                self.minimum_risk_score
                <=
                self.average_risk_score
                <=
                self.maximum_risk_score
            ):
                raise ValueError(
                    "Session Risk Scores must "
                    "satisfy minimum <= average "
                    "<= maximum"
                )

        # ----------------------------------------------------
        # Buckets require summary scores.
        # ----------------------------------------------------

        if (
            self.risk_score_buckets
            and
            available_count != 3
        ):
            raise ValueError(
                "Risk score buckets require "
                "Session AVG/MIN/MAX"
            )

        # ----------------------------------------------------
        # Bucket index must be unique.
        # ----------------------------------------------------

        indexes = [
            bucket.bucket_index
            for bucket
            in self.risk_score_buckets
        ]

        if (
            len(indexes)
            !=
            len(set(indexes))
        ):
            raise ValueError(
                "Duplicate risk score "
                "bucket_index"
            )

        return self


# ============================================================
# SESSION SUMMARY RESPONSE
# ============================================================

class SessionSummaryResponse(
    BaseModel
):
    summary_id: int
    session_id: int

    # ========================================================
    # POSTGUARD RISK SCORE
    # ========================================================

    average_risk_score: (
        float | None
    )

    minimum_risk_score: (
        float | None
    )

    maximum_risk_score: (
        float | None
    )

    risk_score_method: (
        str | None
    )

    # ========================================================
    # DETECTION SUMMARY
    # ========================================================

    detection_count: int
    pose_detected_count: int
    face_detected_count: int

    average_shoulder: (
        float | None
    )

    average_neck: (
        float | None
    )

    # ========================================================
    # RISK EVENT DURATION
    # ========================================================

    low_risk_duration: int
    medium_risk_duration: int
    high_risk_duration: int

    # ========================================================
    # POSTURE ALERT COUNTS
    # ========================================================

    low_risk_alert_count: int
    medium_risk_alert_count: int
    high_risk_alert_count: int

    total_alert_count: int

    most_frequent_alert_event: (
        str | None
    )

    # ========================================================
    # EYE REMINDER COUNTS
    # ========================================================

    eye_alert_count: int
    eye_first_alert_count: int
    eye_repeat_alert_count: int

    # ========================================================
    # BLINK SUMMARY
    # ========================================================

    blink_rate: (
        float | None
    )

    # ========================================================
    # CAMERA / DATA GAP SUMMARY
    # ========================================================

    data_gap_duration: float
    camera_loss_count: int

    model_config = ConfigDict(
        from_attributes=True
    )