from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any


# ==========================================================
# BASELINE STATUS
# ==========================================================

BASELINE_COLLECTING = "COLLECTING"

BASELINE_SUCCESS = "SUCCESS"

BASELINE_NEED_CONFIRMATION = (
    "NEED_CONFIRMATION"
)

BASELINE_FAILED = "FAILED"


# ==========================================================
# CONFIRMATION STATUS
# ==========================================================

CONFIRMATION_NOT_REQUIRED = (
    "NOT_REQUIRED"
)

CONFIRMATION_PENDING = (
    "PENDING"
)

CONFIRMATION_CONFIRMED = (
    "CONFIRMED"
)

CONFIRMATION_REJECTED = (
    "REJECTED"
)


# ==========================================================
# REQUIRED FEATURES
#
# ใช้เฉพาะ Feature ที่ผ่าน Prototype Validation แล้ว
# ==========================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
    "eye_distance",
)


# ==========================================================
# EXPECTED FEATURE STATUS
# ==========================================================

EXPECTED_FEATURE_STATUS = (
    "validated_prototype"
)


# ==========================================================
# CONFIG
# ==========================================================

@dataclass
class PersonalBaselineConfig:
    """
    Configuration สำหรับ Personal Baseline

    target_samples
        จำนวน Valid Samples ที่ต้องการ

    minimum_valid_ratio
        สัดส่วน Frame ที่ผ่านขั้นต่ำ
        เช่น 0.70 = 70%

    shoulder_confirmation_threshold_deg
        ถ้า Shoulder Baseline มีค่าสัมบูรณ์มากกว่า
        threshold นี้
        จะให้ผู้ใช้ยืนยันก่อนใช้งาน

    Stability Thresholds
        เป็นเกณฑ์เริ่มต้นของ Prototype
        ยังไม่ใช่มาตรฐานทางการแพทย์
        และควรปรับหลังการทดลองจริง
    """

    target_samples: int = 60

    minimum_valid_ratio: float = 0.70

    # ------------------------------------------------------
    # User Confirmation
    # ------------------------------------------------------

    shoulder_confirmation_threshold_deg: float = 3.0

    # ------------------------------------------------------
    # Stability
    #
    # ค่าเริ่มต้นสำหรับทดลอง
    # สามารถปรับหลังได้
    # ------------------------------------------------------

    max_shoulder_sd_deg: float = 2.0

    max_neck_lateral_sd_deg: float = 2.0

    max_neck_flexion_sd_deg: float = 3.0

    max_eye_distance_sd_px: float = 5.0


# ==========================================================
# NUMERIC HELPERS
# ==========================================================

def _is_finite_number(
    value: Any,
) -> bool:
    """
    ตรวจว่าค่าเป็นตัวเลขที่ใช้งานได้จริง
    """

    if value is None:
        return False

    try:
        return math.isfinite(
            float(
                value
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


# ==========================================================
# BASIC STATISTICS
# ==========================================================

def _calculate_statistics(
    values: list[float],
) -> dict[str, float | None]:
    """
    คำนวณสถิติของ Feature

    Baseline หลัก:
        Median

    Quality:
        Mean
        SD
        Min
        Max
    """

    if not values:

        return {
            "median": None,
            "mean": None,
            "sd": None,
            "min": None,
            "max": None,
        }

    clean_values = [
        float(
            value
        )
        for value in values
        if _is_finite_number(
            value
        )
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

    # ------------------------------------------------------
    # ใช้ Sample Standard Deviation
    #
    # ถ้ามี Sample เดียว
    # ยังหาค่า SD แบบ sample ไม่ได้
    # ------------------------------------------------------

    if len(
        clean_values
    ) >= 2:

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
            min(
                clean_values
            )
        ),

        "max": float(
            max(
                clean_values
            )
        ),
    }


# ==========================================================
# PERSONAL BASELINE COLLECTOR
# ==========================================================

class PersonalBaselineCollector:
    """
    Personal Baseline Collector สำหรับ PostGuard

    หน้าที่:
    --------
    1. รับ DetectionPipeline Result ทีละ Frame
    2. ตรวจ Context
    3. ตรวจ Feature Validity
    4. เก็บเฉพาะ Valid Samples
    5. เก็บจนครบ target_samples
    6. คำนวณ Median
    7. คำนวณ Stability
    8. Validate Baseline
    9. ระบุว่าต้อง User Confirmation หรือไม่

    Collector ไม่ทำ:
    ----------------
    - Camera Roll Correction
    - MediaPipe Detection
    - Risk Assessment
    - Alert
    - Database Save
    - Session Creation
    """

    # ======================================================
    # INITIALIZE
    # ======================================================

    def __init__(
        self,
        config: PersonalBaselineConfig | None = None,
    ):

        if config is None:

            config = (
                PersonalBaselineConfig()
            )

        self.config = config

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


        # --------------------------------------------------
        # เก็บค่า Feature
        # --------------------------------------------------

        self.samples = {

            "shoulder_tilt": [],

            "neck_lateral_tilt": [],

            "neck_flexion": [],

            "eye_distance": [],
        }


        # --------------------------------------------------
        # เก็บ Timestamp ของ Valid Sample
        # --------------------------------------------------

        self.timestamps: list[float] = []


        # --------------------------------------------------
        # Rejection Counter
        #
        # ใช้ Debug / Validation
        # --------------------------------------------------

        self.rejection_reasons: dict[
            str,
            int
        ] = {}


        # --------------------------------------------------
        # Result
        # --------------------------------------------------

        self.completed = False

        self._result: (
            dict[str, Any]
            | None
        ) = None


    # ======================================================
    # REJECTION LOG
    # ======================================================

    def _reject(
        self,
        reason: str,
    ) -> None:
        """
        บันทึกว่า Frame ถูก Reject เพราะอะไร
        """

        self.rejected_frames += 1


        self.rejection_reasons[
            reason
        ] = (

            self.rejection_reasons.get(
                reason,
                0,
            )

            +

            1
        )


    # ======================================================
    # GET FEATURE
    # ======================================================

    def _extract_feature(
        self,
        detection_result: dict,
        feature_name: str,
    ) -> tuple[
        bool,
        float | None,
        str,
    ]:
        """
        อ่าน Feature จาก DetectionPipeline Contract

        ต้องมี:

        valid = True

        status = validated_prototype

        value = finite number
        """

        features = (
            detection_result.get(
                "features"
            )
            or {}
        )


        feature = (
            features.get(
                feature_name
            )
        )


        if not isinstance(
            feature,
            dict,
        ):

            return (
                False,
                None,
                (
                    f"{feature_name}"
                    "_missing"
                ),
            )


        # --------------------------------------------------
        # VALID?
        # --------------------------------------------------

        if feature.get(
            "valid"
        ) is not True:

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
        # STATUS?
        # --------------------------------------------------

        status = (
            feature.get(
                "status"
            )
        )


        if (
            status
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
        # VALUE?
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
            float(
                value
            ),
            "OK",
        )


    # ======================================================
    # VALIDATE CONTEXT
    # ======================================================

    def _context_allows_sample(
        self,
        detection_result: dict,
    ) -> tuple[
        bool,
        str,
    ]:
        """
        Baseline รับเฉพาะ Context ที่อนุญาตให้ประเมินท่าทาง
        """

        context = (
            detection_result.get(
                "context"
            )
            or {}
        )


        allow = (
            context.get(
                "allow_posture_evaluation"
            )
            is True
        )


        if not allow:

            reason = (
                context.get(
                    "reason"
                )
                or
                "context_not_allowed"
            )

            return (
                False,
                (
                    "context_"
                    f"{reason}"
                ),
            )


        return (
            True,
            "OK",
        )


    # ======================================================
    # PROCESS DETECTION RESULT
    # ======================================================

    def add_detection_result(
        self,
        detection_result: dict,
    ) -> dict[str, Any]:
        """
        รับ Result จาก:

            DetectionPipeline.process_frame()

        Return:
            Progress / Result
        """

        # --------------------------------------------------
        # ถ้าจบแล้ว
        # ไม่เก็บเพิ่ม
        # --------------------------------------------------

        if self.completed:

            return (
                self.get_status()
            )


        self.total_frames += 1


        # ==================================================
        # RESULT TYPE
        # ==================================================

        if not isinstance(
            detection_result,
            dict,
        ):

            self._reject(
                "invalid_detection_result"
            )

            return (
                self.get_status()
            )


        # ==================================================
        # CONTRACT VERSION
        # ==================================================

        contract_version = (
            detection_result.get(
                "contract_version"
            )
        )


        if contract_version != "1.0":

            self._reject(
                "unsupported_contract_version"
            )

            return (
                self.get_status()
            )


        # ==================================================
        # CONTEXT
        # ==================================================

        (
            context_ok,
            context_reason,
        ) = self._context_allows_sample(
            detection_result
        )


        if not context_ok:

            self._reject(
                context_reason
            )

            return (
                self.get_status()
            )


        # ==================================================
        # REQUIRED FEATURES
        # ==================================================

        sample: dict[
            str,
            float
        ] = {}


        for feature_name in (
            REQUIRED_FEATURES
        ):

            (
                valid,
                value,
                reason,
            ) = self._extract_feature(
                detection_result,
                feature_name,
            )


            if not valid:

                self._reject(
                    reason
                )

                return (
                    self.get_status()
                )


            sample[
                feature_name
            ] = float(
                value
            )


        # ==================================================
        # TIMESTAMP
        # ==================================================

        timestamp = (
            detection_result.get(
                "timestamp"
            )
        )


        if _is_finite_number(
            timestamp
        ):

            timestamp_value = float(
                timestamp
            )

        else:

            timestamp_value = (
                float(
                    self.total_frames
                )
            )


        # ==================================================
        # ACCEPT SAMPLE
        # ==================================================

        for feature_name in (
            REQUIRED_FEATURES
        ):

            self.samples[
                feature_name
            ].append(
                sample[
                    feature_name
                ]
            )


        self.timestamps.append(
            timestamp_value
        )


        self.accepted_samples += 1


        # ==================================================
        # COMPLETE?
        # ==================================================

        if (
            self.accepted_samples
            >=
            self.config.target_samples
        ):

            self._result = (
                self._build_result()
            )

            self.completed = True


        return (
            self.get_status()
        )


    # ======================================================
    # VALID RATIO
    # ======================================================

    def _calculate_valid_ratio(
        self,
    ) -> float:
        """
        accepted / total
        """

        if self.total_frames <= 0:

            return 0.0


        return float(

            self.accepted_samples

            /

            self.total_frames
        )


    # ======================================================
    # CALIBRATION DURATION
    # ======================================================

    def _calculate_duration(
        self,
    ) -> float | None:
        """
        ระยะเวลาตั้งแต่ Valid Sample แรก
        ถึง Valid Sample สุดท้าย
        """

        if len(
            self.timestamps
        ) < 2:

            return None


        duration = (

            self.timestamps[-1]

            -

            self.timestamps[0]
        )


        if (
            not math.isfinite(
                duration
            )
            or
            duration < 0
        ):

            return None


        return float(
            duration
        )


    # ======================================================
    # BUILD FEATURE STATS
    # ======================================================

    def _build_feature_statistics(
        self,
    ) -> dict[
        str,
        dict[str, float | None]
    ]:
        """
        คำนวณค่าของทุก Feature
        """

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
    # STABILITY VALIDATION
    # ======================================================

    def _validate_stability(
        self,
        stats: dict[
            str,
            dict[str, float | None]
        ],
    ) -> dict[str, Any]:
        """
        ตรวจ SD ของแต่ละ Feature

        Threshold ตอนนี้เป็น
        Prototype Initial Threshold

        ยังต้องเอาไปทดสอบ Repeatability จริง
        เพื่อปรับต่อ
        """

        issues: list[str] = []


        # --------------------------------------------------
        # Shoulder Tilt
        # --------------------------------------------------

        shoulder_sd = (
            stats[
                "shoulder_tilt"
            ][
                "sd"
            ]
        )


        if (
            shoulder_sd is None

            or

            shoulder_sd
            >
            self.config.max_shoulder_sd_deg
        ):

            issues.append(
                "SHOULDER_TILT_UNSTABLE"
            )


        # --------------------------------------------------
        # Neck Lateral
        # --------------------------------------------------

        neck_lateral_sd = (
            stats[
                "neck_lateral_tilt"
            ][
                "sd"
            ]
        )


        if (
            neck_lateral_sd is None

            or

            neck_lateral_sd
            >
            self.config.max_neck_lateral_sd_deg
        ):

            issues.append(
                "NECK_LATERAL_UNSTABLE"
            )


        # --------------------------------------------------
        # Neck Flexion
        # --------------------------------------------------

        neck_flexion_sd = (
            stats[
                "neck_flexion"
            ][
                "sd"
            ]
        )


        if (
            neck_flexion_sd is None

            or

            neck_flexion_sd
            >
            self.config.max_neck_flexion_sd_deg
        ):

            issues.append(
                "NECK_FLEXION_UNSTABLE"
            )


        # --------------------------------------------------
        # Eye Distance
        # --------------------------------------------------

        eye_distance_sd = (
            stats[
                "eye_distance"
            ][
                "sd"
            ]
        )


        if (
            eye_distance_sd is None

            or

            eye_distance_sd
            >
            self.config.max_eye_distance_sd_px
        ):

            issues.append(
                "EYE_DISTANCE_UNSTABLE"
            )


        return {

            "passed": (
                len(
                    issues
                )
                == 0
            ),

            "issues": issues,
        }


    # ======================================================
    # CONFIRMATION CHECK
    # ======================================================

    def _check_confirmation(
        self,
        stats: dict[
            str,
            dict[str, float | None]
        ],
    ) -> dict[str, Any]:
        """
        ตอนนี้ User Confirmation
        ใช้กับ Shoulder Tilt ก่อน

        IMPORTANT:
        ---------
        Confirmation ไม่ได้แก้ Measurement Error

        เป็นเพียงการถามว่า:
        "ค่าพื้นฐานนี้สอดคล้องกับ
        ท่าปกติของผู้ใช้หรือไม่"
        """

        shoulder_baseline = (
            stats[
                "shoulder_tilt"
            ][
                "median"
            ]
        )


        if shoulder_baseline is None:

            return {

                "required": False,

                "status":
                    CONFIRMATION_NOT_REQUIRED,

                "reason":
                    "SHOULDER_BASELINE_NOT_AVAILABLE",
            }


        if (

            abs(
                shoulder_baseline
            )

            >=

            self.config
            .shoulder_confirmation_threshold_deg

        ):

            return {

                "required": True,

                "status":
                    CONFIRMATION_PENDING,

                "reason":
                    "SHOULDER_BASELINE_TILT",

                "value":
                    float(
                        shoulder_baseline
                    ),

                "threshold":
                    float(
                        self.config
                        .shoulder_confirmation_threshold_deg
                    ),
            }


        return {

            "required": False,

            "status":
                CONFIRMATION_NOT_REQUIRED,

            "reason":
                "NOT_REQUIRED",
        }


    # ======================================================
    # BUILD RESULT
    # ======================================================

    def _build_result(
        self,
    ) -> dict[str, Any]:
        """
        สรุป Personal Baseline หลังเก็บครบ
        """

        stats = (
            self._build_feature_statistics()
        )


        valid_ratio = (
            self._calculate_valid_ratio()
        )


        duration_seconds = (
            self._calculate_duration()
        )


        # ==================================================
        # VALID RATIO
        # ==================================================

        ratio_passed = (

            valid_ratio
            >=
            self.config.minimum_valid_ratio
        )


        # ==================================================
        # STABILITY
        # ==================================================

        stability = (
            self._validate_stability(
                stats
            )
        )


        # ==================================================
        # VALIDATION ISSUES
        # ==================================================

        validation_issues: list[str] = []


        if not ratio_passed:

            validation_issues.append(
                "LOW_VALID_RATIO"
            )


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
            == 0
        )


        # ==================================================
        # FAILED
        # ==================================================

        if not validation_passed:

            confirmation = {

                "required": False,

                "status":
                    CONFIRMATION_NOT_REQUIRED,

                "reason":
                    "VALIDATION_FAILED",
            }


            status = (
                BASELINE_FAILED
            )


        # ==================================================
        # PASSED VALIDATION
        # ==================================================

        else:

            confirmation = (
                self._check_confirmation(
                    stats
                )
            )


            if confirmation[
                "required"
            ]:

                status = (
                    BASELINE_NEED_CONFIRMATION
                )


            else:

                status = (
                    BASELINE_SUCCESS
                )


        # ==================================================
        # BASELINE VALUES
        # ==================================================

        baseline = {

            "shoulder_tilt":
                stats[
                    "shoulder_tilt"
                ][
                    "median"
                ],

            "neck_lateral_tilt":
                stats[
                    "neck_lateral_tilt"
                ][
                    "median"
                ],

            "neck_flexion":
                stats[
                    "neck_flexion"
                ][
                    "median"
                ],

            "eye_distance":
                stats[
                    "eye_distance"
                ][
                    "median"
                ],
        }


        # ==================================================
        # STABILITY VALUES
        # ==================================================

        stability_values = {

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


        # ==================================================
        # RETURN
        # ==================================================

        return {

            "status":
                status,

            "target_samples":
                int(
                    self.config.target_samples
                ),

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
                    valid_ratio
                ),

            "duration_seconds":
                duration_seconds,


            # ----------------------------------------------
            # Personal Baseline
            # ----------------------------------------------

            "baseline":
                baseline,


            # ----------------------------------------------
            # Full Statistics
            # ----------------------------------------------

            "statistics":
                stats,


            # ----------------------------------------------
            # Stability
            # ----------------------------------------------

            "stability":
                stability_values,


            # ----------------------------------------------
            # Validation
            # ----------------------------------------------

            "validation": {

                "passed":
                    validation_passed,

                "minimum_valid_ratio":
                    float(
                        self.config
                        .minimum_valid_ratio
                    ),

                "issues":
                    validation_issues,
            },


            # ----------------------------------------------
            # User Confirmation
            # ----------------------------------------------

            "confirmation":
                confirmation,


            # ----------------------------------------------
            # Debug / Test
            # ----------------------------------------------

            "rejection_reasons":
                dict(
                    self.rejection_reasons
                ),
        }


    # ======================================================
    # GET STATUS
    # ======================================================

    def get_status(
        self,
    ) -> dict[str, Any]:
        """
        ใช้สำหรับ UI แสดง Progress
        """

        if self.completed:

            return dict(
                self._result
            )


        progress = (

            self.accepted_samples

            /

            self.config.target_samples
        )


        progress = max(
            0.0,
            min(
                1.0,
                progress,
            ),
        )


        return {

            "status":
                BASELINE_COLLECTING,

            "sample_count":
                int(
                    self.accepted_samples
                ),

            "target_samples":
                int(
                    self.config.target_samples
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

            "progress":
                float(
                    progress
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
        """
        คืน Result เมื่อ Calibration เสร็จ
        """

        if not self.completed:

            return None


        return dict(
            self._result
        )


    # ======================================================
    # CONFIRM
    # ======================================================

    def confirm(
        self,
    ) -> dict[str, Any]:
        """
        ผู้ใช้ยืนยันว่า Baseline
        ตรงกับท่าปกติของตน

        ใช้ได้เฉพาะตอน
        NEED_CONFIRMATION
        """

        if not self.completed:

            raise RuntimeError(
                "Baseline collection "
                "is not completed."
            )


        if (
            self._result[
                "status"
            ]
            !=
            BASELINE_NEED_CONFIRMATION
        ):

            raise RuntimeError(
                "Baseline does not "
                "require confirmation."
            )


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


        return dict(
            self._result
        )


    # ======================================================
    # REJECT
    # ======================================================

    def reject(
        self,
    ) -> dict[str, Any]:
        """
        ผู้ใช้บอกว่า Baseline ที่พบ
        ไม่ตรงกับท่าปกติของตน

        UI ควรสั่ง Calibration ใหม่
        หลังจากนี้
        """

        if not self.completed:

            raise RuntimeError(
                "Baseline collection "
                "is not completed."
            )


        if (
            self._result[
                "status"
            ]
            !=
            BASELINE_NEED_CONFIRMATION
        ):

            raise RuntimeError(
                "Baseline does not "
                "require confirmation."
            )


        self._result[
            "confirmation"
        ][
            "status"
        ] = (
            CONFIRMATION_REJECTED
        )


        self._result[
            "status"
        ] = (
            BASELINE_FAILED
        )


        self._result[
            "validation"
        ][
            "issues"
        ].append(
            "USER_REJECTED_BASELINE"
        )


        return dict(
            self._result
        )