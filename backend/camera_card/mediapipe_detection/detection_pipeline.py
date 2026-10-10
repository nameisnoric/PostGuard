import math
import time
from pathlib import Path


# ==========================================================
# Detector
# ==========================================================

from .pose.pose_detector import PoseDetector
from .face.face_detector import FaceDetector

from .face.face_points import extract_face_points
from .face.face_orientation import extract_face_orientation


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
# Face Feature Validator
# ==========================================================

from .face.face_feature_validator import (
    validate_face_feature
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
    calculate_eye_distance
)

from .posture.torso_orientation import (
    calculate_torso_orientation
)


# ==========================================================
# Eye
# ==========================================================

from .eye.eye_measurement import (
    calculate_eye_openness
)

from .eye.eye_state import (
    EyeStateDetector
)


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่าเป็นตัวเลขปกติที่ใช้งานได้หรือไม่

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - String ที่แปลงไม่ได้
    """

    if value is None:
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError):
        return False


# ==========================================================
# Feature Result Helper
# ==========================================================

def _invalid_feature(
    reason,
    status="validated",
    unit=None,
    details=None,
):
    """
    Output มาตรฐานเมื่อ Feature ใช้งานไม่ได้
    """

    result = {
        "valid": False,
        "value": None,
        "unit": unit,
        "reason": reason,
        "status": status,
    }

    if details is not None:
        result["details"] = details

    return result


def _valid_feature(
    value,
    unit=None,
    status="validated",
    extra=None,
):
    """
    Output มาตรฐานเมื่อ Feature ใช้งานได้
    """

    if not _is_finite_number(value):

        return _invalid_feature(
            reason="INVALID_RESULT",
            status=status,
            unit=unit,
        )

    result = {
        "valid": True,
        "value": float(value),
        "unit": unit,
        "reason": "OK",
        "status": status,
    }

    if extra is not None:
        result["extra"] = extra

    return result


# ==========================================================
# Detection Pipeline
# ==========================================================

class DetectionPipeline:
    """
    PostGuard Detection Pipeline


    Frame Rule
    ----------

    Input ของ Pipeline ต้องเป็น:

        UNMIRRORED FRAME

    ถ้ามี Camera Roll Correction:

        Raw Frame
            ↓
        Roll Correction
            ↓
        DetectionPipeline


    การ Mirror ต้องเกิดเฉพาะตอน Display:

        Detection Frame
            ↓
        cv2.flip()
            ↓
        Display


    Pipeline นี้ไม่ทำ:
    - Personal Baseline
    - Relative Neck Rotation จาก Baseline
    - RULA
    - Risk
    - Alert
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
        # Camera Card Root
        #
        # detection_pipeline.py
        # อยู่:
        #
        # camera_card/
        #   mediapipe_detection/
        #       detection_pipeline.py
        #
        # parents[1] = camera_card
        # --------------------------------------------------

        camera_card_dir = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        model_dir = (
            camera_card_dir
            /
            "models"
        )

        # --------------------------------------------------
        # Pose Model
        # --------------------------------------------------

        if pose_model_path is None:

            pose_model_path = (
                model_dir
                /
                "pose_landmarker_lite.task"
            )

        # --------------------------------------------------
        # Face Model
        # --------------------------------------------------

        if face_model_path is None:

            face_model_path = (
                model_dir
                /
                "face_landmarker.task"
            )

        # --------------------------------------------------
        # Verify Models
        # --------------------------------------------------

        if not Path(
            pose_model_path
        ).exists():

            raise FileNotFoundError(
                f"Pose model not found: "
                f"{pose_model_path}"
            )

        if not Path(
            face_model_path
        ).exists():

            raise FileNotFoundError(
                f"Face model not found: "
                f"{face_model_path}"
            )

        # --------------------------------------------------
        # Pose Detector
        # --------------------------------------------------

        self.pose_detector = PoseDetector(
            model_path=str(
                pose_model_path
            )
        )

        # --------------------------------------------------
        # Face Detector
        # --------------------------------------------------

        try:

            self.face_detector = FaceDetector(
                model_path=str(
                    face_model_path
                )
            )

        except Exception:

            self.pose_detector.close()

            raise

        # --------------------------------------------------
        # Eye State Detector
        # --------------------------------------------------

        self.eye_state_detector = (
            EyeStateDetector()
        )


    # ======================================================
    # Eye Calibration
    # ======================================================

    def start_eye_calibration(
        self,
        timestamp=None,
    ):
        """
        เริ่ม Open-eye Calibration
        """

        self.eye_state_detector.start_calibration(
            timestamp=timestamp
        )


    def reset_eye_calibration(
        self
    ):
        """
        Reset Eye Calibration
        """

        self.eye_state_detector.reset()


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

        Parameters
        ----------
        frame:
            OpenCV BGR Frame
            ต้องเป็น Unmirrored

        timestamp:
            monotonic timestamp
            ใช้กับ temporal detection

        Returns
        -------
        dict
            Detection Result
        """

        # --------------------------------------------------
        # Validate Frame
        # --------------------------------------------------

        if frame is None:

            raise ValueError(
                "Detection frame is None"
            )

        if not hasattr(
            frame,
            "size"
        ):

            raise ValueError(
                "Detection frame must be a numpy image"
            )

        if frame.size == 0:

            raise ValueError(
                "Detection frame is empty"
            )

        # --------------------------------------------------
        # Timestamp
        # --------------------------------------------------

        if timestamp is None:

            timestamp = (
                time.perf_counter()
            )

        timestamp = float(
            timestamp
        )

        frame_height, frame_width = (
            frame.shape[:2]
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
            pose_points is not None
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
            if face_result is not None
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
                    status="validated",
                )
            )

        else:

            shoulder_tilt = (
                _invalid_feature(
                    reason=shoulder_validation[
                        "reason"
                    ],
                    status="validated",
                    unit="deg",
                    details=shoulder_validation,
                )
            )


        # ==================================================
        # SHOULDER ELEVATION
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

            # ----------------------------------------------
            # IMPORTANT
            #
            # posture_features.py คืน:
            #
            # {
            #     "left": ...,
            #     "right": ...
            # }
            #
            # ไม่ใช่:
            #
            # left_elevation
            # right_elevation
            # ----------------------------------------------

            if elevation_result is None:

                shoulder_elevation = {
                    "valid": False,
                    "left": None,
                    "right": None,
                    "unit": "ratio",
                    "reason": "INVALID_RESULT",
                    "status": "validated",
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

                        "unit": "ratio",
                        "reason": "OK",
                        "status": "validated",
                    }

                else:

                    shoulder_elevation = {
                        "valid": False,
                        "left": None,
                        "right": None,
                        "unit": "ratio",
                        "reason": "INVALID_RESULT",
                        "status": "validated",
                    }

        else:

            shoulder_elevation = {
                "valid": False,
                "left": None,
                "right": None,
                "unit": "ratio",

                "reason": (
                    elevation_validation[
                        "reason"
                    ]
                ),

                "status": "validated",

                "details": (
                    elevation_validation
                ),
            }


        # ==================================================
        # NECK LATERAL TILT
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
                        reason="INVALID_RESULT",
                        status="validated",
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
                        status="validated",

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
                        }
                    )
                )

        else:

            neck_lateral_tilt = (
                _invalid_feature(
                    reason=neck_validation[
                        "reason"
                    ],
                    status="validated",
                    unit="deg",
                    details=neck_validation,
                )
            )


        # ==================================================
        # FORWARD HEAD
        #
        # ยัง Candidate จนกว่า Final Validation
        # จะถูก LOCK อย่างเป็นทางการ
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
                        reason="INVALID_RESULT",
                        status="candidate",
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
                        status="candidate",

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
                        }
                    )
                )

        else:

            forward_head = (
                _invalid_feature(
                    reason=forward_validation[
                        "reason"
                    ],
                    status="candidate",
                    unit="ratio",
                    details=forward_validation,
                )
            )


        # ==================================================
        # TORSO ORIENTATION
        #
        # Experimental
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
                        reason="INVALID_RESULT",
                        status="experimental",
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
                        status="experimental",

                        extra={
                            "world_dx": (
                                torso_result.get(
                                    "world_dx"
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
                        }
                    )
                )

        else:

            torso_orientation = (
                _invalid_feature(
                    reason=torso_validation[
                        "reason"
                    ],
                    status="experimental",
                    unit="deg",
                    details=torso_validation,
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
        # NECK FLEXION / HEAD YAW / HEAD ROLL
        # ==================================================

        if orientation is not None:

            neck_flexion = (
                _valid_feature(

                    orientation.get(
                        "pitch"
                    ),

                    unit="deg",
                    status="validated",
                )
            )

            head_yaw = (
                _valid_feature(

                    orientation.get(
                        "yaw"
                    ),

                    unit="deg",
                    status="candidate",
                )
            )

            head_roll = (
                _valid_feature(

                    orientation.get(
                        "roll"
                    ),

                    unit="deg",
                    status="diagnostic",
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
                    reason=orientation_reason,
                    status="validated",
                    unit="deg",
                    details=orientation_validation,
                )
            )

            head_yaw = (
                _invalid_feature(
                    reason=orientation_reason,
                    status="candidate",
                    unit="deg",
                    details=orientation_validation,
                )
            )

            head_roll = (
                _invalid_feature(
                    reason=orientation_reason,
                    status="diagnostic",
                    unit="deg",
                    details=orientation_validation,
                )
            )


        # ==================================================
        # RELATIVE DISTANCE
        # Inter-Eye Distance / IPD Proxy
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
                        reason="INVALID_RESULT",
                        status="validated",
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
                        status="validated",
                    )
                )

        else:

            eye_distance = (
                _invalid_feature(
                    reason=distance_validation[
                        "reason"
                    ],
                    status="validated",
                    unit="px",
                    details=distance_validation,
                )
            )


        # ==================================================
        # EYE OPENNESS VALIDATION
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
        # ==================================================

        eye_state = (
            self.eye_state_detector.update(
                eye_measurement,
                timestamp=timestamp,
            )
        )


        # ==================================================
        # FINAL OUTPUT
        # ==================================================

        return {

            "timestamp": timestamp,

            # ------------------------------------------------
            # Detection Availability
            # ------------------------------------------------

            "pose_detected": (
                pose_detected
            ),

            "face_detected": (
                face_detected
            ),

            # ------------------------------------------------
            # Posture / Geometry Features
            # ------------------------------------------------

            "features": {

                "shoulder_tilt": (
                    shoulder_tilt
                ),

                "shoulder_elevation": (
                    shoulder_elevation
                ),

                "neck_lateral_tilt": (
                    neck_lateral_tilt
                ),

                "neck_flexion": (
                    neck_flexion
                ),

                # --------------------------------------------
                # IMPORTANT:
                #
                # head_yaw ยังไม่เรียกว่า neck_rotation
                #
                # Neck Rotation ตัวจริงในอนาคตต้องใช้
                # Head + Torso + Personal Baseline
                # --------------------------------------------

                "head_yaw": (
                    head_yaw
                ),

                "head_roll": (
                    head_roll
                ),

                "forward_head": (
                    forward_head
                ),

                "torso_orientation": (
                    torso_orientation
                ),

                "eye_distance": (
                    eye_distance
                ),
            },

            # ------------------------------------------------
            # Eye
            # ------------------------------------------------

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

                "validation": (
                    eye_validation
                ),
            },

            # ------------------------------------------------
            # Selected Landmarks
            #
            # ใช้ Debug / Test เท่านั้น
            # ------------------------------------------------

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
        """
        ปิด MediaPipe resources
        """

        self.pose_detector.close()

        self.face_detector.close()