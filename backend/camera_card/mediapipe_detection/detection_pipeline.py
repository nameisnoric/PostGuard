import math
import time
from pathlib import Path


# ==========================================================
# Detector
# ==========================================================

from .pose.pose_detector import (
    PoseDetector,
)

from .face.face_detector import (
    FaceDetector,
)

from .face.face_points import (
    extract_face_points,
)

from .face.face_orientation import (
    extract_face_orientation,
)


# ==========================================================
# Pose Validators
# ==========================================================

from .pose.pose_validator import (
    validate_shoulder_tilt,
    validate_shoulder_elevation,
    validate_neck_lateral_tilt,
    validate_forward_head,
    validate_torso_orientation,
)


# ==========================================================
# Face Validator
# ==========================================================

from .face.face_feature_validator import (
    validate_face_feature,
)


# ==========================================================
# Posture Features
# ==========================================================

from .posture.posture_features import (
    calculate_shoulder_tilt,
    calculate_shoulder_elevation,
    calculate_neck_lateral_tilt,
    calculate_forward_head,
)

from .posture.relative_distance import (
    calculate_eye_distance,
)

from .posture.torso_orientation import (
    calculate_torso_orientation,
)

from .posture.context_filter import (
    PostureContextFilter,
)


# ==========================================================
# Eye
# ==========================================================

from .eye.eye_measurement import (
    calculate_eye_openness,
)

from .eye.eye_state import (
    EyeStateDetector,
)

from .eye.blink_detector import (
    BlinkDetector,
)

from .eye.eye_closure import (
    EyeClosureDetector,
)


# ==========================================================
# Feature Status
# ==========================================================

STATUS_VALIDATED = (
    "validated_prototype"
)

STATUS_CANDIDATE = (
    "candidate_prototype"
)

STATUS_EXPERIMENTAL = (
    "experimental"
)

STATUS_DIAGNOSTIC = (
    "diagnostic"
)


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(
    value
):
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
# Invalid Feature
# ==========================================================

def _invalid_feature(
    reason,
    status=STATUS_CANDIDATE,
    unit=None,
    details=None,
):
    result = {
        "valid": False,

        "value": None,

        "unit": unit,

        "reason": (
            reason
        ),

        "status": (
            status
        ),
    }

    if details is not None:
        result[
            "details"
        ] = details

    return result


# ==========================================================
# Valid Feature
# ==========================================================

def _valid_feature(
    value,
    unit=None,
    status=STATUS_CANDIDATE,
    extra=None,
):
    if not _is_finite_number(
        value
    ):
        return _invalid_feature(
            reason="INVALID_RESULT",
            status=status,
            unit=unit,
        )

    result = {
        "valid": True,

        "value": float(
            value
        ),

        "unit": unit,

        "reason": "OK",

        "status": (
            status
        ),
    }

    if extra is not None:
        result[
            "extra"
        ] = extra

    return result


# ==========================================================
# Detection Pipeline
# ==========================================================

class DetectionPipeline:
    """
    PostGuard Detection Pipeline

    Input:
        OpenCV BGR Frame แบบ UNMIRRORED

    Pipeline ทำ:
        - Pose Detection
        - Face Detection

        - Context Filter

        - Shoulder Tilt
        - Shoulder Elevation

        - Neck Lateral Tilt
        - Neck Flexion

        - Head Yaw
        - Head Roll

        - Forward Head Experimental

        - Torso Orientation

        - Relative Eye Distance

        - Eye Openness
        - Eye State
        - Blink
        - Long Eye Closure

    Pipeline ไม่ทำ:
        - Personal Baseline Comparison
        - Final Relative Neck Rotation
        - Risk Assessment
        - RULA
        - Sustained Risk
        - Alert
        - Session Summary
    """

    # ======================================================
    # Initialize
    # ======================================================

    def __init__(
        self,
        pose_model_path=None,
        face_model_path=None,
    ):
        # --------------------------------------------------
        # camera_card/
        #   mediapipe_detection/
        #       detection_pipeline.py
        #
        # parents[1] = camera_card
        # --------------------------------------------------

        camera_card_dir = (
            Path(
                __file__
            )
            .resolve()
            .parents[
                1
            ]
        )

        model_dir = (
            camera_card_dir
            /
            "models"
        )

        # ==================================================
        # Pose Model
        # ==================================================

        if pose_model_path is None:
            pose_model_path = (
                model_dir
                /
                "pose_landmarker_lite.task"
            )

        # ==================================================
        # Face Model
        # ==================================================

        if face_model_path is None:
            face_model_path = (
                model_dir
                /
                "face_landmarker.task"
            )

        # ==================================================
        # Verify Files
        # ==================================================

        if not Path(
            pose_model_path
        ).exists():
            raise FileNotFoundError(
                "Pose model not found: "
                f"{pose_model_path}"
            )

        if not Path(
            face_model_path
        ).exists():
            raise FileNotFoundError(
                "Face model not found: "
                f"{face_model_path}"
            )

        # ==================================================
        # Pose Detector
        # ==================================================

        self.pose_detector = (
            PoseDetector(
                model_path=str(
                    pose_model_path
                )
            )
        )

        # ==================================================
        # Face Detector
        # ==================================================

        try:
            self.face_detector = (
                FaceDetector(
                    model_path=str(
                        face_model_path
                    )
                )
            )

        except Exception:
            self.pose_detector.close()
            raise

        # ==================================================
        # Eye Runtime
        # ==================================================

        self.eye_state_detector = (
            EyeStateDetector()
        )

        self.blink_detector = (
            BlinkDetector()
        )

        self.eye_closure_detector = (
            EyeClosureDetector()
        )

        # ==================================================
        # Posture Context Filter
        #
        # ต้องเป็น Instance เดียว
        # และอยู่ข้ามหลาย Frame
        # ==================================================

        self.context_filter = (
            PostureContextFilter()
        )

    # ======================================================
    # Start Eye Calibration
    # ======================================================

    def start_eye_calibration(
        self,
        timestamp=None,
    ):
        self.blink_detector.reset()

        self.eye_closure_detector.reset()

        self.eye_state_detector.start_calibration(
            timestamp=timestamp
        )

    # ======================================================
    # Reset Eye
    # ======================================================

    def reset_eye_calibration(
        self
    ):
        self.eye_state_detector.reset()

        self.blink_detector.reset()

        self.eye_closure_detector.reset()

    # ======================================================
    # Reset Context
    # ======================================================

    def reset_context(
        self
    ):
        """
        เรียกเมื่อ:

        - เริ่ม Session ใหม่
        - เปลี่ยนกล้อง
        - กล้อง reconnect
        """

        self.context_filter.reset()

    # ======================================================
    # Reset Runtime
    # ======================================================

    def reset_runtime(
        self
    ):
        self.reset_eye_calibration()

        self.reset_context()

    # ======================================================
    # Process Frame
    # ======================================================

    def process_frame(
        self,
        frame,
        timestamp=None,
    ):
        """
        ประมวลผล Frame หนึ่งภาพ

        IMPORTANT:

        frame ต้องเป็น UNMIRRORED

        Mirror เฉพาะตอน Display
        """

        # ==================================================
        # Validate Frame
        # ==================================================

        if frame is None:
            raise ValueError(
                "Detection frame is None"
            )

        if not hasattr(
            frame,
            "size"
        ):
            raise ValueError(
                "Detection frame must be "
                "a numpy image"
            )

        if frame.size == 0:
            raise ValueError(
                "Detection frame is empty"
            )

        # ==================================================
        # Timestamp
        # ==================================================

        if timestamp is None:
            timestamp = (
                time.perf_counter()
            )

        timestamp = float(
            timestamp
        )

        frame_height, frame_width = (
            frame.shape[
                :2
            ]
        )

        # ==================================================
        # POSE DETECTION
        # ==================================================

        pose_points = (
            self.pose_detector.detect(
                frame
            )
        )

        pose_detected = (
            pose_points
            is not None
        )

        # ==================================================
        # CONTEXT FILTER
        #
        # IMPORTANT:
        #
        # Context ไม่หยุด Feature Calculation
        #
        # มันเพียงบอก Session/Risk Layer ว่า
        # Frame นี้ควรถูกใช้เพิ่ม Risk Timer หรือไม่
        # ==================================================

        context = (
            self.context_filter.update(
                points=pose_points,

                frame_width=(
                    frame_width
                ),

                frame_height=(
                    frame_height
                ),

                timestamp=(
                    timestamp
                ),
            )
        )

        # ==================================================
        # FACE DETECTION
        # ==================================================

        face_result = (
            self.face_detector.detect(
                frame
            )
        )

        face_landmarks = (
            getattr(
                face_result,
                "face_landmarks",
                None,
            )

            if face_result
            is not None

            else None
        )

        face_detected = bool(
            face_landmarks
        )

        if face_detected:
            face_points = (
                extract_face_points(
                    face_result,
                    frame_width,
                    frame_height,
                )
            )

        else:
            face_points = None

        # ==================================================
        # SHOULDER TILT
        #
        # Validated Prototype
        # ==================================================

        shoulder_validation = (
            validate_shoulder_tilt(
                pose_points
            )
        )

        if shoulder_validation[
            "valid"
        ]:
            shoulder_value = (
                calculate_shoulder_tilt(
                    pose_points[
                        "left_shoulder"
                    ],

                    pose_points[
                        "right_shoulder"
                    ],
                )
            )

            shoulder_tilt = (
                _valid_feature(
                    shoulder_value,

                    unit="deg",

                    status=(
                        STATUS_VALIDATED
                    ),
                )
            )

        else:
            shoulder_tilt = (
                _invalid_feature(
                    reason=(
                        shoulder_validation[
                            "reason"
                        ]
                    ),

                    status=(
                        STATUS_VALIDATED
                    ),

                    unit="deg",

                    details=(
                        shoulder_validation
                    ),
                )
            )

        # ==================================================
        # SHOULDER ELEVATION V2
        #
        # Candidate Prototype
        #
        # ต้องผ่าน Cross-talk Test ใหม่ก่อน Lock
        # ==================================================

        elevation_validation = (
            validate_shoulder_elevation(
                pose_points
            )
        )

        if elevation_validation[
            "valid"
        ]:
            elevation_result = (
                calculate_shoulder_elevation(
                    pose_points.get(
                        "nose"
                    ),

                    pose_points[
                        "left_shoulder"
                    ],

                    pose_points[
                        "right_shoulder"
                    ],
                )
            )

            if elevation_result is None:
                shoulder_elevation = {
                    "valid": False,

                    "left": None,

                    "right": None,

                    "unit": (
                        "ratio"
                    ),

                    "reason": (
                        "INVALID_RESULT"
                    ),

                    "status": (
                        STATUS_CANDIDATE
                    ),
                }

            else:
                left_value = (
                    elevation_result.get(
                        "left"
                    )
                )

                right_value = (
                    elevation_result.get(
                        "right"
                    )
                )

                values_valid = (
                    _is_finite_number(
                        left_value
                    )
                    and
                    _is_finite_number(
                        right_value
                    )
                )

                if values_valid:
                    shoulder_elevation = {
                        "valid": True,

                        "left": float(
                            left_value
                        ),

                        "right": float(
                            right_value
                        ),

                        "unit": (
                            "ratio"
                        ),

                        "reason": "OK",

                        "status": (
                            STATUS_CANDIDATE
                        ),

                        "extra": {
                            "shoulder_width": (
                                elevation_result.get(
                                    "shoulder_width"
                                )
                            ),
                        },
                    }

                else:
                    shoulder_elevation = {
                        "valid": False,

                        "left": None,

                        "right": None,

                        "unit": (
                            "ratio"
                        ),

                        "reason": (
                            "INVALID_RESULT"
                        ),

                        "status": (
                            STATUS_CANDIDATE
                        ),
                    }

        else:
            shoulder_elevation = {
                "valid": False,

                "left": None,

                "right": None,

                "unit": (
                    "ratio"
                ),

                "reason": (
                    elevation_validation[
                        "reason"
                    ]
                ),

                "status": (
                    STATUS_CANDIDATE
                ),

                "details": (
                    elevation_validation
                ),
            }

        # ==================================================
        # NECK LATERAL TILT
        #
        # Validated Prototype
        # ==================================================

        neck_validation = (
            validate_neck_lateral_tilt(
                pose_points
            )
        )

        if neck_validation[
            "valid"
        ]:
            neck_result = (
                calculate_neck_lateral_tilt(
                    pose_points[
                        "left_ear"
                    ],

                    pose_points[
                        "right_ear"
                    ],

                    pose_points[
                        "left_shoulder"
                    ],

                    pose_points[
                        "right_shoulder"
                    ],
                )
            )

            if neck_result is None:
                neck_lateral_tilt = (
                    _invalid_feature(
                        reason=(
                            "INVALID_RESULT"
                        ),

                        status=(
                            STATUS_VALIDATED
                        ),

                        unit="deg",
                    )
                )

            else:
                neck_lateral_tilt = (
                    _valid_feature(
                        neck_result.get(
                            "neck_tilt"
                        ),

                        unit="deg",

                        status=(
                            STATUS_VALIDATED
                        ),

                        extra={
                            "ear_angle": (
                                neck_result.get(
                                    "ear_angle"
                                )
                            ),

                            "shoulder_angle": (
                                neck_result.get(
                                    "shoulder_angle"
                                )
                            ),
                        },
                    )
                )

        else:
            neck_lateral_tilt = (
                _invalid_feature(
                    reason=(
                        neck_validation[
                            "reason"
                        ]
                    ),

                    status=(
                        STATUS_VALIDATED
                    ),

                    unit="deg",

                    details=(
                        neck_validation
                    ),
                )
            )

        # ==================================================
        # FORWARD HEAD
        #
        # Experimental
        #
        # ยังไม่ใช้ Risk / Alert
        # ==================================================

        forward_validation = (
            validate_forward_head(
                pose_points
            )
        )

        if forward_validation[
            "valid"
        ]:
            forward_result = (
                calculate_forward_head(
                    pose_points[
                        "nose"
                    ],

                    pose_points[
                        "left_shoulder"
                    ],

                    pose_points[
                        "right_shoulder"
                    ],
                )
            )

            if forward_result is None:
                forward_head = (
                    _invalid_feature(
                        reason=(
                            "INVALID_RESULT"
                        ),

                        status=(
                            STATUS_EXPERIMENTAL
                        ),

                        unit="ratio",
                    )
                )

            else:
                forward_head = (
                    _valid_feature(
                        forward_result.get(
                            "forward_head"
                        ),

                        unit="ratio",

                        status=(
                            STATUS_EXPERIMENTAL
                        ),

                        extra={
                            "nose_z": (
                                forward_result.get(
                                    "nose_z"
                                )
                            ),

                            "shoulder_mid_z": (
                                forward_result.get(
                                    "shoulder_mid_z"
                                )
                            ),

                            "shoulder_width": (
                                forward_result.get(
                                    "shoulder_width"
                                )
                            ),
                        },
                    )
                )

        else:
            forward_head = (
                _invalid_feature(
                    reason=(
                        forward_validation[
                            "reason"
                        ]
                    ),

                    status=(
                        STATUS_EXPERIMENTAL
                    ),

                    unit="ratio",

                    details=(
                        forward_validation
                    ),
                )
            )

        # ==================================================
        # TORSO ORIENTATION
        #
        # Experimental
        #
        # ใช้ Shoulder World X/Z
        # ไม่ใช้ Hip/Waist
        #
        # ต้องผ่าน Torso Cross-talk Test
        # ==================================================

        torso_validation = (
            validate_torso_orientation(
                pose_points
            )
        )

        if torso_validation[
            "valid"
        ]:
            torso_result = (
                calculate_torso_orientation(
                    pose_points
                )
            )

            if torso_result is None:
                torso_orientation = (
                    _invalid_feature(
                        reason=(
                            "INVALID_RESULT"
                        ),

                        status=(
                            STATUS_EXPERIMENTAL
                        ),

                        unit="deg",
                    )
                )

            else:
                torso_orientation = (
                    _valid_feature(
                        torso_result.get(
                            "angle"
                        ),

                        unit="deg",

                        status=(
                            STATUS_EXPERIMENTAL
                        ),

                        extra={
                            "world_dx": (
                                torso_result.get(
                                    "world_dx"
                                )
                            ),

                            "world_dy": (
                                torso_result.get(
                                    "world_dy"
                                )
                            ),

                            "world_dz": (
                                torso_result.get(
                                    "world_dz"
                                )
                            ),

                            "width_3d": (
                                torso_result.get(
                                    "width_3d"
                                )
                            ),

                            "width_xz": (
                                torso_result.get(
                                    "width_xz"
                                )
                            ),

                            "depth_ratio": (
                                torso_result.get(
                                    "depth_ratio"
                                )
                            ),
                        },
                    )
                )

        else:
            torso_orientation = (
                _invalid_feature(
                    reason=(
                        torso_validation[
                            "reason"
                        ]
                    ),

                    status=(
                        STATUS_EXPERIMENTAL
                    ),

                    unit="deg",

                    details=(
                        torso_validation
                    ),
                )
            )

        # ==================================================
        # FACE ORIENTATION
        # ==================================================

        orientation_validation = (
            validate_face_feature(
                face_points,

                required_points=(
                    "nose_tip",
                    "chin",

                    "right_eye_outer",
                    "right_eye_inner",

                    "left_eye_outer",
                    "left_eye_inner",

                    "right_face",
                    "left_face",
                ),
            )
        )

        orientation = None

        if orientation_validation[
            "valid"
        ]:
            orientation = (
                extract_face_orientation(
                    face_result
                )
            )

        # ==================================================
        # NECK FLEXION
        # HEAD YAW
        # HEAD ROLL
        # ==================================================

        if orientation is not None:

            # ----------------------------------------------
            # Neck Flexion
            # ----------------------------------------------

            neck_flexion = (
                _valid_feature(
                    orientation.get(
                        "pitch"
                    ),

                    unit="deg",

                    status=(
                        STATUS_VALIDATED
                    ),
                )
            )

            # ----------------------------------------------
            # Head Yaw
            #
            # ยังไม่ใช่ Final Neck Rotation
            # ----------------------------------------------

            head_yaw = (
                _valid_feature(
                    orientation.get(
                        "yaw"
                    ),

                    unit="deg",

                    status="candidate",
                )
            )

            # ----------------------------------------------
            # Head Roll
            # ----------------------------------------------

            head_roll = (
                _valid_feature(
                    orientation.get(
                        "roll"
                    ),

                    unit="deg",

                    status=(
                        STATUS_DIAGNOSTIC
                    ),
                )
            )

        else:

            if not orientation_validation[
                "valid"
            ]:
                orientation_reason = (
                    orientation_validation[
                        "reason"
                    ]
                )

            else:
                orientation_reason = (
                    "ORIENTATION_NOT_AVAILABLE"
                )

            neck_flexion = (
                _invalid_feature(
                    reason=(
                        orientation_reason
                    ),

                    status=(
                        STATUS_VALIDATED
                    ),

                    unit="deg",

                    details=(
                        orientation_validation
                    ),
                )
            )

            head_yaw = (
                _invalid_feature(
                    reason=(
                        orientation_reason
                    ),

                    status="candidate",

                    unit="deg",

                    details=(
                        orientation_validation
                    ),
                )
            )

            head_roll = (
                _invalid_feature(
                    reason=(
                        orientation_reason
                    ),

                    status=(
                        STATUS_DIAGNOSTIC
                    ),

                    unit="deg",

                    details=(
                        orientation_validation
                    ),
                )
            )

        # ==================================================
        # RELATIVE EYE DISTANCE
        #
        # Validated Prototype
        #
        # Pixel relative proxy
        # ไม่ใช่ Physical IPD
        # ==================================================

        distance_validation = (
            validate_face_feature(
                face_points,

                required_points=(
                    "left_eye_outer",
                    "left_eye_inner",

                    "right_eye_outer",
                    "right_eye_inner",
                ),
            )
        )

        if distance_validation[
            "valid"
        ]:
            distance_result = (
                calculate_eye_distance(
                    face_points
                )
            )

            if distance_result is None:
                eye_distance = (
                    _invalid_feature(
                        reason=(
                            "INVALID_RESULT"
                        ),

                        status=(
                            STATUS_VALIDATED
                        ),

                        unit="px",
                    )
                )

            else:
                eye_distance = (
                    _valid_feature(
                        distance_result.get(
                            "eye_distance_px"
                        ),

                        unit="px",

                        status=(
                            STATUS_VALIDATED
                        ),
                    )
                )

        else:
            eye_distance = (
                _invalid_feature(
                    reason=(
                        distance_validation[
                            "reason"
                        ]
                    ),

                    status=(
                        STATUS_VALIDATED
                    ),

                    unit="px",

                    details=(
                        distance_validation
                    ),
                )
            )

        # ==================================================
        # EYE VALIDATION
        # ==================================================

        eye_validation = (
            validate_face_feature(
                face_points,

                required_points=(
                    "right_eye_outer",
                    "right_eye_inner",
                    "right_eye_upper",
                    "right_eye_lower",

                    "left_eye_outer",
                    "left_eye_inner",
                    "left_eye_upper",
                    "left_eye_lower",
                ),
            )
        )

        # ==================================================
        # EYE MEASUREMENT
        # ==================================================

        eye_measurement = None

        if eye_validation[
            "valid"
        ]:
            eye_measurement = (
                calculate_eye_openness(
                    face_points
                )
            )

        # ==================================================
        # EYE STATE
        #
        # OPEN / CLOSED / UNKNOWN
        # ==================================================

        eye_state = (
            self.eye_state_detector.update(
                eye_measurement,

                timestamp=(
                    timestamp
                ),
            )
        )

        # ==================================================
        # BLINK
        # ==================================================

        blink_result = (
            self.blink_detector.update(
                eye_state,

                eye_measurement=(
                    eye_measurement
                ),

                timestamp=(
                    timestamp
                ),
            )
        )

        # ==================================================
        # LONG EYE CLOSURE
        # ==================================================

        closure_result = (
            self.eye_closure_detector.update(
                eye_state,

                eye_measurement=(
                    eye_measurement
                ),

                timestamp=(
                    timestamp
                ),
            )
        )

        # ==================================================
        # FINAL OUTPUT
        #
        # Detection Contract Version 1.0
        # ==================================================

        return {

            # ----------------------------------------------
            # Contract
            # ----------------------------------------------

            "contract_version": (
                "1.0"
            ),

            # ----------------------------------------------
            # Timestamp
            # ----------------------------------------------

            "timestamp": (
                timestamp
            ),

            # ----------------------------------------------
            # Detection Availability
            # ----------------------------------------------

            "pose_detected": (
                pose_detected
            ),

            "face_detected": (
                face_detected
            ),

            # ==============================================
            # CONTEXT
            #
            # Session / Risk Layer
            # ต้องดู allow_posture_evaluation
            # ==============================================

            "context": (
                context
            ),

            # ==============================================
            # FEATURES
            # ==============================================

            "features": {

                # ------------------------------------------
                # Shoulder
                # ------------------------------------------

                "shoulder_tilt": (
                    shoulder_tilt
                ),

                "shoulder_elevation": (
                    shoulder_elevation
                ),

                # ------------------------------------------
                # Neck
                # ------------------------------------------

                "neck_lateral_tilt": (
                    neck_lateral_tilt
                ),

                "neck_flexion": (
                    neck_flexion
                ),

                # ------------------------------------------
                # Head Orientation
                # ------------------------------------------

                "head_yaw": (
                    head_yaw
                ),

                "head_roll": (
                    head_roll
                ),

                # ------------------------------------------
                # Experimental
                # ------------------------------------------

                "forward_head": (
                    forward_head
                ),

                "torso_orientation": (
                    torso_orientation
                ),

                # ------------------------------------------
                # Distance
                # ------------------------------------------

                "eye_distance": (
                    eye_distance
                ),
            },

            # ==============================================
            # EYE
            # ==============================================

            "eye": {

                "measurement_valid": (
                    eye_measurement
                    is not None
                ),

                "measurement": (
                    eye_measurement
                ),

                "state": (
                    eye_state
                ),

                "blink": (
                    blink_result
                ),

                "closure": (
                    closure_result
                ),

                "validation": (
                    eye_validation
                ),
            },

            # ==============================================
            # LANDMARKS
            #
            # Debug / Test เท่านั้น
            # ==============================================

            "landmarks": {

                "pose": (
                    pose_points
                ),

                "face": (
                    face_points
                ),
            },
        }

    # ======================================================
    # Close
    # ======================================================

    def close(
        self
    ):
        self.pose_detector.close()

        self.face_detector.close()