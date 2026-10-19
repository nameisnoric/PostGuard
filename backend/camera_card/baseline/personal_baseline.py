from __future__ import annotations

import copy
import math
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable


# ==========================================================
# BASELINE STATUS
# ==========================================================

BASELINE_COLLECTING = "COLLECTING"
BASELINE_SUCCESS = "SUCCESS"
BASELINE_NEED_CONFIRMATION = "NEED_CONFIRMATION"
BASELINE_FAILED = "FAILED"


# ==========================================================
# CONFIRMATION STATUS
# ==========================================================

CONFIRMATION_NOT_REQUIRED = "NOT_REQUIRED"
CONFIRMATION_PENDING = "PENDING"
CONFIRMATION_CONFIRMED = "CONFIRMED"
CONFIRMATION_REJECTED = "REJECTED"

CONFIRMATION_REASON_USER_REVIEW = "USER_BASELINE_REVIEW"


# ==========================================================
# REQUIRED FEATURES
# ==========================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
)

EXPECTED_FEATURE_STATUS = "validated_prototype"
EXPECTED_CONTEXT_STATE = "VALID"
EXPECTED_CONTRACT_VERSION = "1.0"

EXPECTED_FEATURE_UNITS = {
    "shoulder_tilt": "deg",
    "neck_lateral_tilt": "deg",
    "neck_flexion": "deg",
    "eye_distance": "px",
}


# ==========================================================
# CONFIG
# ==========================================================

@dataclass
class PersonalBaselineConfig:
    """
    Personal Baseline Configuration

    Final Prototype Design
    ----------------------
    1. ต้องมี Valid Samples อย่างน้อย target_samples
    2. ต้องเก็บข้อมูลอย่างน้อย min_calibration_seconds
    3. เก็บ Valid Samples ต่อแม้เกิน target_samples
    4. max_calibration_seconds เป็น Runtime Guard
    5. Technical Validation ผ่านแล้วต้อง User Confirm ทุก Session

    หมายเหตุ:
    Quality thresholds ด้านล่างยังเป็น Prototype thresholds
    ไม่ใช่มาตรฐานทางการแพทย์
    """

    # Minimum amount of valid data
    target_samples: int = 60

    # Measurement quality
    minimum_valid_ratio: float = 0.70

    # Temporal coverage
    min_calibration_seconds: float = 15.0
    max_calibration_seconds: float = 30.0

    # Stability thresholds
    max_shoulder_sd_deg: float = 2.0
    max_neck_lateral_sd_deg: float = 2.0
    max_neck_flexion_sd_deg: float = 3.0
    max_eye_distance_sd_px: float = 5.0

    def __post_init__(self) -> None:

        # --------------------------------------------------
        # TARGET SAMPLES
        # --------------------------------------------------

        if (
            isinstance(self.target_samples, bool)
            or not isinstance(self.target_samples, int)
            or self.target_samples < 2
        ):
            raise ValueError(
                "target_samples must be an integer >= 2"
            )

        # --------------------------------------------------
        # FINITE NUMERIC CONFIG
        # --------------------------------------------------

        numeric_config = {
            "minimum_valid_ratio":
                self.minimum_valid_ratio,

            "min_calibration_seconds":
                self.min_calibration_seconds,

            "max_calibration_seconds":
                self.max_calibration_seconds,

            "max_shoulder_sd_deg":
                self.max_shoulder_sd_deg,

            "max_neck_lateral_sd_deg":
                self.max_neck_lateral_sd_deg,

            "max_neck_flexion_sd_deg":
                self.max_neck_flexion_sd_deg,

            "max_eye_distance_sd_px":
                self.max_eye_distance_sd_px,
        }

        for name, value in numeric_config.items():

            try:
                numeric_value = float(value)

            except (TypeError, ValueError) as exc:

                raise ValueError(
                    f"{name} must be a finite number"
                ) from exc

            if not math.isfinite(numeric_value):

                raise ValueError(
                    f"{name} must be a finite number"
                )

        # --------------------------------------------------
        # VALID RATIO
        # --------------------------------------------------

        if not (
            0.0
            <
            float(self.minimum_valid_ratio)
            <=
            1.0
        ):
            raise ValueError(
                "minimum_valid_ratio must be in range (0, 1]"
            )

        # --------------------------------------------------
        # TIME
        # --------------------------------------------------

        if (
            float(self.min_calibration_seconds)
            <= 0.0
        ):
            raise ValueError(
                "min_calibration_seconds must be > 0"
            )

        if (
            float(self.max_calibration_seconds)
            <=
            float(self.min_calibration_seconds)
        ):
            raise ValueError(
                "max_calibration_seconds must be greater "
                "than min_calibration_seconds"
            )

        # --------------------------------------------------
        # STABILITY THRESHOLDS
        # --------------------------------------------------

        stability_thresholds = (
            float(self.max_shoulder_sd_deg),

            float(
                self.max_neck_lateral_sd_deg
            ),

            float(
                self.max_neck_flexion_sd_deg
            ),

            float(
                self.max_eye_distance_sd_px
            ),
        )

        if any(
            value < 0.0
            for value in stability_thresholds
        ):
            raise ValueError(
                "stability thresholds must be >= 0"
            )


# ==========================================================
# NUMERIC HELPERS
# ==========================================================

def _is_finite_number(
    value: Any,
) -> bool:
    """
    ตรวจว่าค่าเป็นตัวเลขที่ใช้งานได้จริง
    และไม่ใช่ NaN / Infinity
    """

    if value is None:
        return False

    try:
        return math.isfinite(
            float(value)
        )

    except (TypeError, ValueError):
        return False


# ==========================================================
# STATISTICS
# ==========================================================

def _calculate_statistics(
    values: list[float],
) -> dict[str, float | None]:
    """
    Personal Baseline ใช้ Median เป็นค่า Reference หลัก

    เก็บเพิ่ม:
    - Mean
    - Sample SD
    - Min
    - Max

    เพื่อ Technical Validation และ Debug
    """

    clean_values = [
        float(value)
        for value in values
        if _is_finite_number(value)
    ]

    if not clean_values:

        return {
            "median": None,
            "mean": None,
            "sd": None,
            "min": None,
            "max": None,
        }

    median_value = float(
        statistics.median(
            clean_values
        )
    )

    mean_value = float(
        statistics.mean(
            clean_values
        )
    )

    if len(clean_values) >= 2:

        sd_value = float(
            statistics.stdev(
                clean_values
            )
        )

    else:

        sd_value = 0.0

    return {
        "median": median_value,
        "mean": mean_value,
        "sd": sd_value,
        "min": float(
            min(clean_values)
        ),
        "max": float(
            max(clean_values)
        ),
    }


# ==========================================================
# PERSONAL BASELINE COLLECTOR
# ==========================================================

class PersonalBaselineCollector:
    """
    Personal Baseline Collector สำหรับ PostGuard

    หน้าที่
    -------
    1. รับ DetectionPipeline Result ทีละ Frame
    2. ตรวจ Detection Contract
    3. ตรวจ Context
    4. ตรวจ Feature Validity / Status / Unit / Value
    5. เก็บเฉพาะ Valid Samples
    6. เก็บอย่างน้อย 60 Valid Samples
    7. เก็บข้อมูลอย่างน้อย 15 วินาที
    8. คำนวณ Median / Mean / SD / Min / Max
    9. Technical Validation
    10. Validation PASS -> User Review ทุก Session
    11. Session ใช้ Baseline ได้เฉพาะ SUCCESS

    Collector ไม่ทำ
    ----------------
    - Camera Roll Correction
    - MediaPipe Detection
    - Risk Assessment
    - Alert
    - Database Save
    - Session Creation
    """

    # ======================================================
    # INIT
    # ======================================================

    def __init__(
        self,
        config: PersonalBaselineConfig | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ):

        if config is None:
            config = (
                PersonalBaselineConfig()
            )

        self.config = config

        # Runtime จริงใช้ time.monotonic()
        #
        # Unit Test สามารถ Inject FakeClock
        # เพื่อไม่ต้องรอ 15 / 30 วินาทีจริง
        self._clock = (
            monotonic_fn
            or
            time.monotonic
        )

        self.reset()

    # ======================================================
    # RESET
    # ======================================================

    def reset(
        self,
    ) -> None:
        """
        เริ่ม Calibration ใหม่ทั้งหมด
        """

        self.total_frames = 0
        self.accepted_samples = 0
        self.rejected_frames = 0

        self.samples: dict[
            str,
            list[float],
        ] = {
            feature_name: []
            for feature_name
            in REQUIRED_FEATURES
        }

        # --------------------------------------------------
        # เวลา Valid Samples
        # --------------------------------------------------

        self.valid_sample_monotonic_times: list[
            float
        ] = []

        # --------------------------------------------------
        # Detection Timestamp
        #
        # ใช้ Trace / Debug เท่านั้น
        # ไม่ใช้คำนวณ Calibration Time
        # --------------------------------------------------

        self.detection_timestamps: list[
            float | None
        ] = []

        # --------------------------------------------------
        # Reject Counters
        # --------------------------------------------------

        self.rejection_reasons: dict[
            str,
            int,
        ] = {}

        # --------------------------------------------------
        # Calibration Start Time
        # --------------------------------------------------

        self._started_monotonic: (
            float
            | None
        ) = None

        # --------------------------------------------------
        # Result
        #
        # completed=True หมายถึง
        # Collection + Technical Validation จบแล้ว
        #
        # NEED_CONFIRMATION ก็ completed=True
        # เพราะไม่เก็บ Sample ต่อแล้ว
        # --------------------------------------------------

        self.completed = False

        self._result: (
            dict[str, Any]
            | None
        ) = None

    # ======================================================
    # CLOCK
    # ======================================================

    def _now(
        self,
    ) -> float:

        value = float(
            self._clock()
        )

        if not math.isfinite(value):

            raise RuntimeError(
                "monotonic clock returned "
                "a non-finite value"
            )

        return value

    def _ensure_started(
        self,
    ) -> None:

        if (
            self._started_monotonic
            is None
        ):

            self._started_monotonic = (
                self._now()
            )

    def _elapsed_seconds(
        self,
    ) -> float:

        if (
            self._started_monotonic
            is None
        ):
            return 0.0

        return max(
            0.0,

            float(
                self._now()
                -
                self._started_monotonic
            ),
        )

    # ======================================================
    # COLLECTION CONDITIONS
    # ======================================================

    def _minimum_collection_met(
        self,
    ) -> bool:
        """
        Baseline พร้อม Technical Validation
        เมื่อครบทั้ง:

        1. Valid Samples >= target_samples
        2. Elapsed >= min_calibration_seconds
        """

        return bool(
            self.accepted_samples
            >=
            self.config.target_samples

            and

            self._elapsed_seconds()
            >=
            self.config.min_calibration_seconds
        )

    def _timed_out(
        self,
    ) -> bool:

        return bool(
            self._elapsed_seconds()
            >=
            self.config.max_calibration_seconds
        )

    # ======================================================
    # REJECTION LOG
    # ======================================================

    def _reject(
        self,
        reason: str,
    ) -> None:

        safe_reason = str(
            reason
            or
            "unknown_rejection"
        )

        self.rejected_frames += 1

        self.rejection_reasons[
            safe_reason
        ] = (
            self.rejection_reasons.get(
                safe_reason,
                0,
            )
            +
            1
        )

    # ======================================================
    # CONTEXT CONTRACT
    # ======================================================

    def _context_allows_sample(
        self,
        context: Any,
    ) -> tuple[
        bool,
        str,
    ]:

        # --------------------------------------------------
        # Contract Guard
        # --------------------------------------------------

        if not isinstance(
            context,
            dict,
        ):

            return (
                False,
                "invalid_context_contract",
            )

        state = (
            context.get(
                "state"
            )
        )

        # --------------------------------------------------
        # Context State
        # --------------------------------------------------

        if (
            state
            !=
            EXPECTED_CONTEXT_STATE
        ):

            reason = (
                context.get(
                    "reason"
                )
                or
                state
                or
                "unknown"
            )

            return (
                False,
                f"context_state_{reason}",
            )

        # --------------------------------------------------
        # Evaluation Permission
        # --------------------------------------------------

        if (
            context.get(
                "allow_posture_evaluation"
            )
            is not True
        ):

            reason = (
                context.get(
                    "reason"
                )
                or
                "not_allowed"
            )

            return (
                False,
                f"context_{reason}",
            )

        return (
            True,
            "OK",
        )

    # ======================================================
    # FEATURE CONTRACT
    # ======================================================

    def _extract_feature(
        self,
        features: dict[str, Any],
        feature_name: str,
    ) -> tuple[
        bool,
        float | None,
        str,
    ]:

        # --------------------------------------------------
        # Missing Feature
        # --------------------------------------------------

        if (
            feature_name
            not in features
        ):

            return (
                False,
                None,
                f"{feature_name}_missing",
            )

        feature = (
            features.get(
                feature_name
            )
        )

        # --------------------------------------------------
        # Contract Guard
        # --------------------------------------------------

        if not isinstance(
            feature,
            dict,
        ):

            return (
                False,
                None,
                (
                    f"{feature_name}_"
                    "invalid_contract"
                ),
            )

        # --------------------------------------------------
        # Valid
        # --------------------------------------------------

        if (
            feature.get(
                "valid"
            )
            is not True
        ):

            reason = (
                feature.get(
                    "reason"
                )
                or
                "invalid"
            )

            return (
                False,
                None,
                (
                    f"{feature_name}_"
                    f"{reason}"
                ),
            )

        # --------------------------------------------------
        # Validation Status
        # --------------------------------------------------

        if (
            feature.get(
                "status"
            )
            !=
            EXPECTED_FEATURE_STATUS
        ):

            return (
                False,
                None,
                (
                    f"{feature_name}_"
                    "not_validated"
                ),
            )

        # --------------------------------------------------
        # Unit
        # --------------------------------------------------

        expected_unit = (
            EXPECTED_FEATURE_UNITS[
                feature_name
            ]
        )

        actual_unit = (
            feature.get(
                "unit"
            )
        )

        if (
            actual_unit
            !=
            expected_unit
        ):

            return (
                False,
                None,
                (
                    f"{feature_name}_"
                    "invalid_unit_"
                    f"{actual_unit}"
                ),
            )

        # --------------------------------------------------
        # Value
        # --------------------------------------------------

        value = (
            feature.get(
                "value"
            )
        )

        if not _is_finite_number(
            value
        ):

            return (
                False,
                None,
                (
                    f"{feature_name}_"
                    "invalid_value"
                ),
            )

        return (
            True,
            float(value),
            "OK",
        )

    # ======================================================
    # ADD DETECTION RESULT
    # ======================================================

    def add_detection_result(
        self,
        detection_result: Any,
    ) -> dict[str, Any]:
        """
        รับ DetectionPipeline Result หนึ่ง Frame

        Completion:
        -----------
        accepted_samples >= target_samples
        AND
        elapsed_seconds >= min_calibration_seconds

        Timeout:
        --------
        elapsed_seconds >= max_calibration_seconds
        ก่อน Completion Conditions จะครบ
        """

        # --------------------------------------------------
        # Already Completed
        # --------------------------------------------------

        if self.completed:

            return self.get_status()

        # --------------------------------------------------
        # Start Timer
        # --------------------------------------------------

        self._ensure_started()

        # --------------------------------------------------
        # Timeout ก่อนรับ Frame ใหม่
        #
        # Frame หลังหมดเวลา
        # จะไม่ถูกเอามาช่วยให้ Calibration ผ่านย้อนหลัง
        # --------------------------------------------------

        if self._timed_out():

            self._fail_collection(
                "CALIBRATION_TIMEOUT"
            )

            return self.get_status()

        # --------------------------------------------------
        # Processed Frame Counter
        # --------------------------------------------------

        self.total_frames += 1

        # --------------------------------------------------
        # Detection Result Contract
        # --------------------------------------------------

        if not isinstance(
            detection_result,
            dict,
        ):

            self._reject(
                "invalid_detection_result_contract"
            )

            return (
                self._after_processed_frame()
            )

        # --------------------------------------------------
        # Contract Version
        # --------------------------------------------------

        if (
            detection_result.get(
                "contract_version"
            )
            !=
            EXPECTED_CONTRACT_VERSION
        ):

            self._reject(
                "unsupported_contract_version"
            )

            return (
                self._after_processed_frame()
            )

        # --------------------------------------------------
        # Context
        # --------------------------------------------------

        context = (
            detection_result.get(
                "context"
            )
        )

        (
            context_ok,
            context_reason,
        ) = (
            self._context_allows_sample(
                context
            )
        )

        if not context_ok:

            self._reject(
                context_reason
            )

            return (
                self._after_processed_frame()
            )

        # --------------------------------------------------
        # Features Contract
        # --------------------------------------------------

        features = (
            detection_result.get(
                "features"
            )
        )

        if not isinstance(
            features,
            dict,
        ):

            self._reject(
                "invalid_features_contract"
            )

            return (
                self._after_processed_frame()
            )

        # --------------------------------------------------
        # Required Features
        # --------------------------------------------------

        sample: dict[
            str,
            float,
        ] = {}

        for feature_name in REQUIRED_FEATURES:

            (
                valid,
                value,
                reason,
            ) = (
                self._extract_feature(
                    features,
                    feature_name,
                )
            )

            if not valid:

                self._reject(
                    reason
                )

                return (
                    self._after_processed_frame()
                )

            sample[
                feature_name
            ] = float(value)

        # --------------------------------------------------
        # Valid Sample Receive Time
        # --------------------------------------------------

        valid_received_at = (
            self._now()
        )

        # --------------------------------------------------
        # Store Feature Values
        # --------------------------------------------------

        for feature_name in REQUIRED_FEATURES:

            self.samples[
                feature_name
            ].append(
                sample[
                    feature_name
                ]
            )

        # --------------------------------------------------
        # Store Real Monotonic Time
        # --------------------------------------------------

        self.valid_sample_monotonic_times.append(
            valid_received_at
        )

        # --------------------------------------------------
        # Detection Timestamp
        #
        # Debug / Trace only
        # --------------------------------------------------

        detection_timestamp = (
            detection_result.get(
                "timestamp"
            )
        )

        if _is_finite_number(
            detection_timestamp
        ):

            detection_timestamp_value: (
                float
                | None
            ) = float(
                detection_timestamp
            )

        else:

            detection_timestamp_value = None

        self.detection_timestamps.append(
            detection_timestamp_value
        )

        # --------------------------------------------------
        # Accepted Counter
        #
        # ไม่มีการหยุดที่ 60
        # เก็บต่อจนเวลาครบ
        # --------------------------------------------------

        self.accepted_samples += 1

        return (
            self._after_processed_frame()
        )

    # ======================================================
    # AFTER FRAME
    # ======================================================

    def _after_processed_frame(
        self,
    ) -> dict[str, Any]:
        """
        หลัง Accept หรือ Reject Frame

        1. ถ้าครบ Samples + Time
           -> Technical Validation

        2. ถ้ายังไม่ครบและ Timeout
           -> FAILED

        3. ไม่เช่นนั้น
           -> COLLECTING
        """

        # --------------------------------------------------
        # Collection Conditions Complete
        # --------------------------------------------------

        if self._minimum_collection_met():

            self._result = (
                self._build_result()
            )

            self.completed = True

            return self.get_status()

        # --------------------------------------------------
        # Timeout
        # --------------------------------------------------

        if self._timed_out():

            self._fail_collection(
                "CALIBRATION_TIMEOUT"
            )

        return self.get_status()

    # ======================================================
    # VALID RATIO
    # ======================================================

    def _calculate_valid_ratio(
        self,
    ) -> float:

        if self.total_frames <= 0:

            return 0.0

        return float(
            self.accepted_samples
            /
            self.total_frames
        )

    # ======================================================
    # VALID SAMPLE SPAN
    # ======================================================

    def _calculate_valid_sample_span(
        self,
    ) -> float | None:
        """
        เวลาระหว่าง Valid Sample แรก
        กับ Valid Sample สุดท้าย

        ไม่ใช่ Total Calibration Elapsed
        """

        if (
            len(
                self.valid_sample_monotonic_times
            )
            <
            2
        ):

            return None

        duration = (
            self.valid_sample_monotonic_times[-1]
            -
            self.valid_sample_monotonic_times[0]
        )

        if (
            not math.isfinite(
                duration
            )
            or
            duration < 0.0
        ):

            return None

        return float(
            duration
        )

    # ======================================================
    # FEATURE STATISTICS
    # ======================================================

    def _build_feature_statistics(
        self,
    ) -> dict[
        str,
        dict[
            str,
            float | None,
        ],
    ]:

        return {
            feature_name:
                _calculate_statistics(
                    self.samples[
                        feature_name
                    ]
                )

            for feature_name
            in REQUIRED_FEATURES
        }

    # ======================================================
    # BASELINE VALUES
    # ======================================================

    @staticmethod
    def _build_baseline_values(
        stats: dict[
            str,
            dict[
                str,
                float | None,
            ],
        ],
    ) -> dict[
        str,
        float | None,
    ]:

        return {
            feature_name:
                stats[
                    feature_name
                ][
                    "median"
                ]

            for feature_name
            in REQUIRED_FEATURES
        }

    # ======================================================
    # STABILITY VALIDATION
    # ======================================================

    def _validate_stability(
        self,
        stats: dict[
            str,
            dict[
                str,
                float | None,
            ],
        ],
    ) -> dict[str, Any]:

        issues: list[str] = []

        checks = (
            (
                "shoulder_tilt",
                self.config
                .max_shoulder_sd_deg,
                "SHOULDER_TILT_UNSTABLE",
            ),

            (
                "neck_lateral_tilt",
                self.config
                .max_neck_lateral_sd_deg,
                "NECK_LATERAL_UNSTABLE",
            ),

            (
                "neck_flexion",
                self.config
                .max_neck_flexion_sd_deg,
                "NECK_FLEXION_UNSTABLE",
            ),

            (
                "eye_distance",
                self.config
                .max_eye_distance_sd_px,
                "EYE_DISTANCE_UNSTABLE",
            ),
        )

        for (
            feature_name,
            max_sd,
            issue_name,
        ) in checks:

            sd_value = (
                stats[
                    feature_name
                ][
                    "sd"
                ]
            )

            if (
                sd_value is None
                or
                sd_value
                >
                float(max_sd)
            ):

                issues.append(
                    issue_name
                )

        return {
            "passed":
                len(issues) == 0,

            "issues":
                issues,
        }

    # ======================================================
    # BUILD TECHNICAL RESULT
    # ======================================================

    def _build_result(
        self,
    ) -> dict[str, Any]:
        """
        เรียกเมื่อครบ:
        - target_samples
        - min_calibration_seconds

        Technical PASS
        -> NEED_CONFIRMATION ทุกครั้ง

        Technical FAIL
        -> FAILED
        """

        stats = (
            self._build_feature_statistics()
        )

        baseline = (
            self._build_baseline_values(
                stats
            )
        )

        valid_ratio = (
            self._calculate_valid_ratio()
        )

        stability = (
            self._validate_stability(
                stats
            )
        )

        validation_issues: list[
            str
        ] = []

        # --------------------------------------------------
        # Valid Ratio
        # --------------------------------------------------

        if (
            valid_ratio
            <
            self.config.minimum_valid_ratio
        ):

            validation_issues.append(
                "LOW_VALID_RATIO"
            )

        # --------------------------------------------------
        # Stability
        # --------------------------------------------------

        if not stability[
            "passed"
        ]:

            validation_issues.extend(
                stability[
                    "issues"
                ]
            )

        validation_passed = (
            len(
                validation_issues
            )
            ==
            0
        )

        # --------------------------------------------------
        # Technical PASS
        # --------------------------------------------------

        if validation_passed:

            status = (
                BASELINE_NEED_CONFIRMATION
            )

            failure_reason = None

            confirmation = {
                "required": True,

                "status":
                    CONFIRMATION_PENDING,

                "reason":
                    CONFIRMATION_REASON_USER_REVIEW,
            }

        # --------------------------------------------------
        # Technical FAIL
        # --------------------------------------------------

        else:

            status = (
                BASELINE_FAILED
            )

            failure_reason = (
                "VALIDATION_FAILED"
            )

            confirmation = {
                "required": False,

                "status":
                    CONFIRMATION_NOT_REQUIRED,

                "reason":
                    "VALIDATION_FAILED",
            }

        return self._compose_result(
            status=
                status,

            failure_reason=
                failure_reason,

            usable_baseline=
                None,

            stats=
                stats,

            baseline=
                baseline,

            validation_passed=
                validation_passed,

            validation_issues=
                validation_issues,

            confirmation=
                confirmation,
        )

    # ======================================================
    # STABILITY VALUES
    # ======================================================

    def _stability_values(
        self,
        stats: dict[
            str,
            dict[
                str,
                float | None,
            ],
        ],
    ) -> dict[
        str,
        float | None,
    ]:

        return {
            "shoulder_tilt_sd":
                stats[
                    "shoulder_tilt"
                ][
                    "sd"
                ],

            "neck_lateral_tilt_sd":
                stats[
                    "neck_lateral_tilt"
                ][
                    "sd"
                ],

            "neck_flexion_sd":
                stats[
                    "neck_flexion"
                ][
                    "sd"
                ],

            "eye_distance_sd":
                stats[
                    "eye_distance"
                ][
                    "sd"
                ],
        }

    # ======================================================
    # COMPOSE RESULT
    # ======================================================

    def _compose_result(
        self,
        *,
        status: str,
        failure_reason: str | None,
        usable_baseline: dict[
            str,
            float,
        ] | None,
        stats: dict[
            str,
            dict[
                str,
                float | None,
            ],
        ],
        baseline: dict[
            str,
            float | None,
        ],
        validation_passed: bool,
        validation_issues: list[str],
        confirmation: dict[str, Any],
    ) -> dict[str, Any]:

        valid_sample_span = (
            self._calculate_valid_sample_span()
        )

        return {
            # ----------------------------------------------
            # Final State
            # ----------------------------------------------

            "status":
                status,

            "ready_for_session":
                (
                    status
                    ==
                    BASELINE_SUCCESS
                ),

            "usable_baseline":
                copy.deepcopy(
                    usable_baseline
                ),

            "failure_reason":
                failure_reason,

            # ----------------------------------------------
            # Collection Requirements
            # ----------------------------------------------

            "target_samples":
                int(
                    self.config
                    .target_samples
                ),

            "min_calibration_seconds":
                float(
                    self.config
                    .min_calibration_seconds
                ),

            "max_calibration_seconds":
                float(
                    self.config
                    .max_calibration_seconds
                ),

            # ----------------------------------------------
            # Counts
            # ----------------------------------------------

            "sample_count":
                int(
                    self.accepted_samples
                ),

            "total_frames":
                int(
                    self.total_frames
                ),

            "rejected_frames":
                int(
                    self.rejected_frames
                ),

            "valid_ratio":
                float(
                    self._calculate_valid_ratio()
                ),

            # ----------------------------------------------
            # Timing
            # ----------------------------------------------

            "valid_sample_span_seconds":
                valid_sample_span,

            # Compatibility alias
            #
            # duration_seconds เดิมมีความหมาย
            # เท่ากับ valid sample span
            "duration_seconds":
                valid_sample_span,

            "elapsed_seconds":
                float(
                    self._elapsed_seconds()
                ),

            # ----------------------------------------------
            # Candidate Baseline
            #
            # ห้าม Session ใช้ field นี้ตรง ๆ
            # ----------------------------------------------

            "baseline":
                copy.deepcopy(
                    baseline
                ),

            # ----------------------------------------------
            # Debug / Quality Data
            # ----------------------------------------------

            "statistics":
                copy.deepcopy(
                    stats
                ),

            "stability":
                self._stability_values(
                    stats
                ),

            # ----------------------------------------------
            # Technical Validation
            # ----------------------------------------------

            "validation": {
                "passed":
                    bool(
                        validation_passed
                    ),

                "minimum_valid_ratio":
                    float(
                        self.config
                        .minimum_valid_ratio
                    ),

                "issues":
                    list(
                        validation_issues
                    ),
            },

            # ----------------------------------------------
            # User Decision
            # ----------------------------------------------

            "confirmation":
                copy.deepcopy(
                    confirmation
                ),

            # ----------------------------------------------
            # Debug Rejections
            # ----------------------------------------------

            "rejection_reasons":
                dict(
                    self.rejection_reasons
                ),
        }

    # ======================================================
    # EARLY FAILURE
    # ======================================================

    def _build_early_failure_result(
        self,
        reason: str,
    ) -> dict[str, Any]:
        """
        เช่น:
        CALIBRATION_TIMEOUT

        Candidate Baseline จาก Partial Samples
        มีไว้ Debug เท่านั้น
        ห้ามนำไปสร้าง Session
        """

        stats = (
            self._build_feature_statistics()
        )

        candidate_baseline = (
            self._build_baseline_values(
                stats
            )
        )

        return self._compose_result(
            status=
                BASELINE_FAILED,

            failure_reason=
                reason,

            usable_baseline=
                None,

            stats=
                stats,

            baseline=
                candidate_baseline,

            validation_passed=
                False,

            validation_issues=[
                reason
            ],

            confirmation={
                "required": False,

                "status":
                    CONFIRMATION_NOT_REQUIRED,

                "reason":
                    "VALIDATION_FAILED",
            },
        )

    def _fail_collection(
        self,
        reason: str,
    ) -> None:

        self._result = (
            self._build_early_failure_result(
                reason
            )
        )

        self.completed = True

    # ======================================================
    # GET STATUS
    # ======================================================

    def get_status(
        self,
    ) -> dict[str, Any]:

        if self.completed:

            return copy.deepcopy(
                self._result
            )

        elapsed = (
            self._elapsed_seconds()
        )

        # --------------------------------------------------
        # Sample Progress
        # --------------------------------------------------

        sample_progress = min(
            1.0,

            (
                self.accepted_samples
                /
                self.config.target_samples
            ),
        )

        # --------------------------------------------------
        # Time Progress
        # --------------------------------------------------

        time_progress = min(
            1.0,

            (
                elapsed
                /
                self.config
                .min_calibration_seconds
            ),
        )

        # --------------------------------------------------
        # Overall Progress
        #
        # ต้องครบทั้ง Sample + Time
        # --------------------------------------------------

        progress = min(
            sample_progress,
            time_progress,
        )

        valid_sample_span = (
            self._calculate_valid_sample_span()
        )

        return {
            "status":
                BASELINE_COLLECTING,

            "ready_for_session":
                False,

            "usable_baseline":
                None,

            "sample_count":
                int(
                    self.accepted_samples
                ),

            "target_samples":
                int(
                    self.config
                    .target_samples
                ),

            "total_frames":
                int(
                    self.total_frames
                ),

            "rejected_frames":
                int(
                    self.rejected_frames
                ),

            "valid_ratio":
                float(
                    self._calculate_valid_ratio()
                ),

            "sample_progress":
                float(
                    sample_progress
                ),

            "time_progress":
                float(
                    time_progress
                ),

            "progress":
                float(
                    progress
                ),

            "elapsed_seconds":
                float(
                    elapsed
                ),

            "valid_sample_span_seconds":
                valid_sample_span,

            # Compatibility alias
            "duration_seconds":
                valid_sample_span,

            "min_calibration_seconds":
                float(
                    self.config
                    .min_calibration_seconds
                ),

            "max_calibration_seconds":
                float(
                    self.config
                    .max_calibration_seconds
                ),

            "rejection_reasons":
                dict(
                    self.rejection_reasons
                ),
        }

    # ======================================================
    # GET RESULT
    # ======================================================

    def get_result(
        self,
    ) -> dict[str, Any] | None:

        if not self.completed:

            return None

        return copy.deepcopy(
            self._result
        )

    # ======================================================
    # SESSION SAFETY GATE
    # ======================================================

    def is_ready_for_session(
        self,
    ) -> bool:

        return bool(
            self.completed

            and

            self._result
            is not None

            and

            self._result.get(
                "status"
            )
            ==
            BASELINE_SUCCESS

            and

            self._result.get(
                "ready_for_session"
            )
            is True
        )

    def get_usable_baseline(
        self,
    ) -> dict[
        str,
        float,
    ]:
        """
        DB / Session Integration
        ต้องใช้เมธอดนี้เท่านั้น

        COLLECTING
        NEED_CONFIRMATION
        FAILED

        จะไม่สามารถคืน Baseline
        ไปสร้าง Session ได้
        """

        if not self.is_ready_for_session():

            current_status = (
                self._result.get(
                    "status"
                )

                if self._result

                else
                BASELINE_COLLECTING
            )

            raise RuntimeError(
                "Personal Baseline is not "
                "ready for Session. "
                f"status={current_status}"
            )

        usable = (
            self._result.get(
                "usable_baseline"
            )
        )

        if not isinstance(
            usable,
            dict,
        ):

            raise RuntimeError(
                "Usable baseline is missing"
            )

        result: dict[
            str,
            float,
        ] = {}

        for feature_name in REQUIRED_FEATURES:

            value = (
                usable.get(
                    feature_name
                )
            )

            if not _is_finite_number(
                value
            ):

                raise RuntimeError(
                    "Usable baseline contains "
                    f"invalid {feature_name}"
                )

            result[
                feature_name
            ] = float(
                value
            )

        return result

    # ======================================================
    # CONFIRM
    # ======================================================

    def confirm(
        self,
    ) -> dict[str, Any]:
        """
        User ยืนยันว่า Candidate นี้
        เป็น Starting Posture ที่ต้องการใช้
        สำหรับ Session ปัจจุบัน

        ไม่ได้หมายความว่า:
        - ท่านี้ปลอดภัย
        - ท่านี้ปกติทางการแพทย์
        """

        if not self.completed:

            raise RuntimeError(
                "Baseline collection "
                "is not completed."
            )

        if (
            self._result is None
            or
            self._result.get(
                "status"
            )
            !=
            BASELINE_NEED_CONFIRMATION
        ):

            raise RuntimeError(
                "Baseline does not "
                "require confirmation."
            )

        # --------------------------------------------------
        # Technical Validation Safety
        # --------------------------------------------------

        if (
            self._result.get(
                "validation",
                {},
            ).get(
                "passed"
            )
            is not True
        ):

            raise RuntimeError(
                "Cannot confirm a baseline "
                "that failed technical validation."
            )

        # --------------------------------------------------
        # Candidate
        # --------------------------------------------------

        candidate = (
            self._result.get(
                "baseline"
            )
        )

        if not isinstance(
            candidate,
            dict,
        ):

            raise RuntimeError(
                "Candidate baseline is missing."
            )

        usable: dict[
            str,
            float,
        ] = {}

        for feature_name in REQUIRED_FEATURES:

            value = (
                candidate.get(
                    feature_name
                )
            )

            if not _is_finite_number(
                value
            ):

                raise RuntimeError(
                    "Candidate baseline contains "
                    f"invalid {feature_name}"
                )

            usable[
                feature_name
            ] = float(
                value
            )

        # --------------------------------------------------
        # Confirmation
        # --------------------------------------------------

        self._result[
            "confirmation"
        ][
            "status"
        ] = (
            CONFIRMATION_CONFIRMED
        )

        self._result[
            "status"
        ] = (
            BASELINE_SUCCESS
        )

        self._result[
            "ready_for_session"
        ] = True

        self._result[
            "usable_baseline"
        ] = copy.deepcopy(
            usable
        )

        self._result[
            "failure_reason"
        ] = None

        return copy.deepcopy(
            self._result
        )

    # ======================================================
    # REJECT
    # ======================================================

    def reject(
        self,
    ) -> dict[str, Any]:
        """
        ผู้ใช้ไม่ยอมรับ Candidate Baseline

        IMPORTANT:
        Technical Validation ยังคงผลเดิม

        User Reject != Measurement Failure
        """

        if not self.completed:

            raise RuntimeError(
                "Baseline collection "
                "is not completed."
            )

        if (
            self._result is None
            or
            self._result.get(
                "status"
            )
            !=
            BASELINE_NEED_CONFIRMATION
        ):

            raise RuntimeError(
                "Baseline does not "
                "require confirmation."
            )

        # --------------------------------------------------
        # User Decision
        # --------------------------------------------------

        self._result[
            "confirmation"
        ][
            "status"
        ] = (
            CONFIRMATION_REJECTED
        )

        # --------------------------------------------------
        # Final Usability State
        # --------------------------------------------------

        self._result[
            "status"
        ] = (
            BASELINE_FAILED
        )

        self._result[
            "ready_for_session"
        ] = False

        self._result[
            "usable_baseline"
        ] = None

        self._result[
            "failure_reason"
        ] = (
            "USER_REJECTED_BASELINE"
        )

        # IMPORTANT:
        # ไม่แก้ validation["passed"]
        # ไม่เพิ่ม USER_REJECTED_BASELINE
        # เข้า validation["issues"]

        return copy.deepcopy(
            self._result
        )
