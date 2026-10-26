import math
import time
from pathlib import Path

from app.vision.mediapipe_detection.pose.pose_detector import (
    PoseDetector,
)
from app.vision.mediapipe_detection.face.face_detector import (
    FaceDetector,
)
from app.vision.mediapipe_detection.face.face_points import (
    extract_face_points,
)
from app.vision.mediapipe_detection.face.face_orientation import (
    extract_face_orientation,
)

from app.vision.mediapipe_detection.pose.pose_validator import (
    validate_shoulder_tilt,
    validate_neck_lateral_tilt,
)
from app.vision.mediapipe_detection.face.face_feature_validator import (
    validate_face_feature,
)

from app.vision.mediapipe_detection.posture.context_filter import (
    PostureContextFilter,
)
from app.vision.mediapipe_detection.posture.posture_features import (
    calculate_shoulder_tilt,
    calculate_neck_lateral_tilt,
)
from app.vision.mediapipe_detection.posture.relative_distance import (
    calculate_eye_distance,
)


# ==========================================================
# Detection Contract
# ==========================================================

DETECTION_CONTRACT_VERSION = "1.0"

VALIDATED_STATUS = "validated_prototype"
EXPERIMENTAL_STATUS = "experimental"


# ==========================================================
# Face Landmark Requirements
# ==========================================================

EYE_DISTANCE_FACE_POINTS = (
    "left_eye_outer",
    "left_eye_inner",
    "right_eye_inner",
    "right_eye_outer",
)


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(value):
    """
    Return True only for a usable finite numeric value.

    bool is deliberately rejected even though bool is
    a subclass of int.
    """

    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


# ==========================================================
# Detection Feature Contract
# ==========================================================

def _valid_feature(
    value,
    unit,
    *,
    status=VALIDATED_STATUS,
    details=None,
):
    """
    Build a valid Detection Contract feature.

    IMPORTANT:
    This function must only be called after the caller has
    already confirmed that value is finite.
    """

    return {
        "valid": True,
        "value": float(value),
        "unit": unit,
        "reason": "OK",
        "status": status,
        **(
            {
                "details": details,
            }
            if details is not None
            else {}
        ),
    }


def _invalid_feature(
    *,
    unit,
    reason,
    status=VALIDATED_STATUS,
    details=None,
):
    """
    Build an invalid Detection Contract feature.

    Invalid features never expose a numeric value.

    The specific reason is preserved so downstream layers
    can distinguish landmark failure from measurement failure.
    """

    return {
        "valid": False,
        "value": None,
        "unit": unit,
        "reason": reason,
        "status": status,
        **(
            {
                "details": details,
            }
            if details is not None
            else {}
        ),
    }


# ==========================================================
# Detection Service
# ==========================================================

class DetectionService:
    """
    Desktop Detection Adapter.

    Responsibilities
    ----------------
    1. Run Pose / Face detection.
    2. Validate landmarks per feature.
    3. Calculate detection features.
    4. Track posture context:
           UNKNOWN
           TRANSITION
           VALID
    5. Return Detection Contract v1.0.

    This service does NOT:
    - compare Personal Baseline
    - calculate risk
    - calculate RULA
    - manage Risk Event
    - send alerts

    Those responsibilities belong to downstream layers.
    """

    def __init__(self):
        model_dir = (
            Path(__file__).resolve().parents[1]
            / "vision"
            / "models"
        )

        pose_model = (
            model_dir
            / "pose_landmarker_lite.task"
        )

        face_model = (
            model_dir
            / "face_landmarker.task"
        )

        self.pose_detector = PoseDetector(
            model_path=str(pose_model)
        )

        try:
            self.face_detector = FaceDetector(
                model_path=str(face_model)
            )

        except Exception:
            self.pose_detector.close()
            raise

        # --------------------------------------------------
        # Stateful posture context
        # --------------------------------------------------
        #
        # Context controls POSTURE evaluation eligibility.
        #
        # It does not globally disable:
        # - Eye Distance
        # - Eye State
        # - Blink
        #
        # Those measurements have their own validity /
        # eligibility rules.
        # --------------------------------------------------

        self.context_filter = (
            PostureContextFilter()
        )

    # ======================================================
    # Runtime Reset
    # ======================================================

    def reset_runtime(self):
        """
        Break temporal continuity of Detection state.

        Use when:
        - starting a monitoring session
        - resuming after pause
        - changing camera
        - otherwise breaking frame continuity

        Blink runtime state is managed separately.
        """

        self.context_filter.reset()

    # ======================================================
    # Shoulder Tilt
    # ======================================================

    @staticmethod
    def _detect_shoulder_tilt(
        pose_points,
    ):
        validation = (
            validate_shoulder_tilt(
                pose_points
            )
        )

        if not validation["valid"]:
            feature = _invalid_feature(
                unit="deg",
                reason=validation["reason"],
                details=validation,
            )

            return (
                None,
                feature,
            )

        value = calculate_shoulder_tilt(
            pose_points.get(
                "left_shoulder"
            ),
            pose_points.get(
                "right_shoulder"
            ),
        )

        # Landmark validity does not guarantee that the
        # measurement function returned a usable number.
        if not _is_finite_number(value):
            feature = _invalid_feature(
                unit="deg",
                reason="SHOULDER_TILT_MEASUREMENT_INVALID",
                details=validation,
            )

            return (
                None,
                feature,
            )

        feature = _valid_feature(
            value,
            "deg",
            details=validation,
        )

        return (
            feature["value"],
            feature,
        )

    # ======================================================
    # Neck Lateral Tilt
    # ======================================================

    @staticmethod
    def _detect_neck_lateral_tilt(
        pose_points,
    ):
        validation = (
            validate_neck_lateral_tilt(
                pose_points
            )
        )

        if not validation["valid"]:
            feature = _invalid_feature(
                unit="deg",
                reason=validation["reason"],
                details=validation,
            )

            return (
                None,
                None,
                feature,
            )

        measurement = (
            calculate_neck_lateral_tilt(
                pose_points.get(
                    "left_ear"
                ),
                pose_points.get(
                    "right_ear"
                ),
                pose_points.get(
                    "left_shoulder"
                ),
                pose_points.get(
                    "right_shoulder"
                ),
            )
        )

        if not isinstance(
            measurement,
            dict,
        ):
            feature = _invalid_feature(
                unit="deg",
                reason="NECK_LATERAL_MEASUREMENT_NOT_AVAILABLE",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        if "neck_tilt" not in measurement:
            feature = _invalid_feature(
                unit="deg",
                reason="NECK_LATERAL_VALUE_MISSING",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        value = measurement.get(
            "neck_tilt"
        )

        if not _is_finite_number(value):
            feature = _invalid_feature(
                unit="deg",
                reason="NECK_LATERAL_VALUE_INVALID",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        feature = _valid_feature(
            value,
            "deg",
            details=validation,
        )

        return (
            feature["value"],
            measurement,
            feature,
        )

    # ======================================================
    # Neck Flexion
    # ======================================================

    @staticmethod
    def _detect_neck_flexion(
        face_result,
        face_detected,
    ):
        """
        Experimental Face Orientation pitch.

        IMPORTANT:
        The current face_orientation implementation itself
        defines this measurement as experimental.

        Therefore:
        - it may be exposed through Detection Contract v1.0;
        - downstream compatibility is preserved;
        - but DetectionService does NOT claim that this
          measurement is a validated prototype.

        Validation here means only:
        "Was a usable orientation measurement produced?"

        It does NOT mean:
        "Has neck-flexion accuracy been validated?"
        """

        if not face_detected:
            feature = _invalid_feature(
                unit="deg",
                reason="FACE_NOT_FOUND",
                status=EXPERIMENTAL_STATUS,
            )

            return (
                None,
                feature,
            )

        orientation = (
            extract_face_orientation(
                face_result
            )
        )

        if not isinstance(
            orientation,
            dict,
        ):
            feature = _invalid_feature(
                unit="deg",
                reason="FACE_ORIENTATION_NOT_AVAILABLE",
                status=EXPERIMENTAL_STATUS,
            )

            return (
                None,
                feature,
            )

        if "pitch" not in orientation:
            feature = _invalid_feature(
                unit="deg",
                reason="FACE_ORIENTATION_PITCH_MISSING",
                status=EXPERIMENTAL_STATUS,
                details={
                    "orientation_available": True,
                },
            )

            return (
                None,
                feature,
            )

        value = orientation.get(
            "pitch"
        )

        if not _is_finite_number(value):
            feature = _invalid_feature(
                unit="deg",
                reason="FACE_ORIENTATION_PITCH_INVALID",
                status=EXPERIMENTAL_STATUS,
                details={
                    "orientation_available": True,
                },
            )

            return (
                None,
                feature,
            )

        feature = _valid_feature(
            value,
            "deg",
            status=EXPERIMENTAL_STATUS,
            details={
                "orientation_available": True,
                "singular": orientation.get(
                    "singular"
                ),
                "rotation_det": orientation.get(
                    "rotation_det"
                ),
                "scale": orientation.get(
                    "scale"
                ),
            },
        )

        return (
            feature["value"],
            feature,
        )

    # ======================================================
    # Eye Distance
    # ======================================================

    @staticmethod
    def _detect_eye_distance(
        face_points,
    ):
        """
        Calculate Inter-Eye Distance / IPD Proxy.

        IMPORTANT:
        This is independent from PostureContextFilter.

        Context TRANSITION / UNKNOWN does not automatically
        invalidate this raw measurement.

        Whether the measurement is suitable for relative
        Screen Distance classification is a SEPARATE
        eligibility decision downstream.
        """

        validation = (
            validate_face_feature(
                face_points,
                required_points=(
                    EYE_DISTANCE_FACE_POINTS
                ),
            )
        )

        if not validation["valid"]:
            feature = _invalid_feature(
                unit="px",
                reason=validation["reason"],
                details=validation,
            )

            return (
                None,
                None,
                feature,
            )

        measurement = (
            calculate_eye_distance(
                face_points
            )
        )

        if not isinstance(
            measurement,
            dict,
        ):
            feature = _invalid_feature(
                unit="px",
                reason="EYE_DISTANCE_MEASUREMENT_NOT_AVAILABLE",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        if "eye_distance_px" not in measurement:
            feature = _invalid_feature(
                unit="px",
                reason="EYE_DISTANCE_VALUE_MISSING",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        value = measurement.get(
            "eye_distance_px"
        )

        if not _is_finite_number(value):
            feature = _invalid_feature(
                unit="px",
                reason="EYE_DISTANCE_VALUE_INVALID",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        if value <= 1e-6:
            feature = _invalid_feature(
                unit="px",
                reason="EYE_DISTANCE_NON_POSITIVE",
                details=validation,
            )

            return (
                None,
                measurement,
                feature,
            )

        feature = _valid_feature(
            value,
            "px",
            details=validation,
        )

        return (
            feature["value"],
            measurement,
            feature,
        )

    # ======================================================
    # Process Frame
    # ======================================================

    def process_frame(
        self,
        frame,
    ):
        if (
            frame is None
            or not hasattr(
                frame,
                "size",
            )
            or frame.size == 0
        ):
            raise ValueError(
                "Invalid camera frame"
            )

        timestamp = time.time()

        frame_height, frame_width = (
            frame.shape[:2]
        )

        # ==================================================
        # 1. Pose Detection
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
        # 2. Posture Context
        # ==================================================
        #
        # Context is based on Pose and is stateful.
        #
        # It controls whether Current Posture Assessment
        # may evaluate POSTURE on this frame.
        #
        # Feature extraction still happens independently.
        # ==================================================

        context = (
            self.context_filter.update(
                points=pose_points,
                frame_width=frame_width,
                frame_height=frame_height,
                timestamp=timestamp,
            )
        )

        # ==================================================
        # 3. Face Detection
        # ==================================================

        face_result = (
            self.face_detector.detect(
                frame
            )
        )

        face_detected = bool(
            face_result is not None
            and getattr(
                face_result,
                "face_landmarks",
                None,
            )
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
        # 4. Shoulder Tilt
        # ==================================================

        (
            shoulder_tilt,
            shoulder_feature,
        ) = self._detect_shoulder_tilt(
            pose_points
        )

        # ==================================================
        # 5. Neck Lateral Tilt
        # ==================================================

        (
            neck_value,
            neck_lateral_tilt,
            neck_lateral_feature,
        ) = (
            self._detect_neck_lateral_tilt(
                pose_points
            )
        )

        # ==================================================
        # 6. Neck Flexion
        # ==================================================

        (
            neck_flexion,
            neck_flexion_feature,
        ) = self._detect_neck_flexion(
            face_result,
            face_detected,
        )

        # ==================================================
        # 7. Eye Distance
        # ==================================================

        (
            eye_distance,
            eye_measurement,
            eye_distance_feature,
        ) = self._detect_eye_distance(
            face_points
        )

        # ==================================================
        # 8. Feature Contract
        # ==================================================

        features = {
            "shoulder_tilt": (
                shoulder_feature
            ),
            "neck_lateral_tilt": (
                neck_lateral_feature
            ),
            "neck_flexion": (
                neck_flexion_feature
            ),
            "eye_distance": (
                eye_distance_feature
            ),
        }

        # ==================================================
        # 9. Detection Contract v1.0
        # ==================================================

        return {
            "contract_version": (
                DETECTION_CONTRACT_VERSION
            ),

            "timestamp": float(
                timestamp
            ),

            # ----------------------------------------------
            # Context Contract
            # ----------------------------------------------

            "context": context,

            # ----------------------------------------------
            # Feature Contract
            # ----------------------------------------------

            "features": features,

            # ----------------------------------------------
            # Raw / Compatibility Data
            # ----------------------------------------------

            "pose_points": (
                pose_points
            ),

            "pose_detected": (
                pose_detected
            ),

            "face_detected": (
                face_detected
            ),

            "face_result": (
                face_result
            ),

            "face_points": (
                face_points
            ),

            # ----------------------------------------------
            # Legacy Compatibility Keys
            # ----------------------------------------------
            #
            # Existing Monitoring / Baseline code may still
            # consume these keys directly.
            # ----------------------------------------------

            "shoulder_tilt": (
                shoulder_tilt
            ),

            "neck_lateral_tilt": (
                neck_lateral_tilt
            ),

            "neck_flexion": (
                neck_flexion
            ),

            "eye_distance": (
                eye_distance
            ),

            # ----------------------------------------------
            # Useful Diagnostic Measurements
            # ----------------------------------------------

            "eye_distance_measurement": (
                eye_measurement
            ),

            "neck_lateral_value": (
                neck_value
            ),
        }

    # ======================================================
    # Close
    # ======================================================

    def close(self):
        """
        Release MediaPipe resources.

        Detector cleanup is attempted independently so that
        one cleanup failure does not prevent the other
        detector from being released.
        """

        try:
            self.context_filter.reset()

        finally:
            try:
                self.pose_detector.close()

            finally:
                self.face_detector.close()