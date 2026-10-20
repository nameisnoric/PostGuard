import math
import time
from pathlib import Path

from app.vision.mediapipe_detection.pose.pose_detector import PoseDetector
from app.vision.mediapipe_detection.face.face_detector import FaceDetector
from app.vision.mediapipe_detection.face.face_points import extract_face_points
from app.vision.mediapipe_detection.face.face_orientation import (
    extract_face_orientation,
)
from app.vision.mediapipe_detection.posture.posture_features import (
    calculate_shoulder_tilt,
    calculate_neck_lateral_tilt
)
from app.vision.mediapipe_detection.posture.relative_distance import (
    calculate_eye_distance,
)


VALIDATED_STATUS = "validated_prototype"


def _baseline_feature(value, unit, reason="OK"):
    """Build the validated feature contract consumed by PersonalBaselineCollector."""
    valid = (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
    return {
        "valid": valid,
        "value": float(value) if valid else None,
        "unit": unit,
        "reason": "OK" if valid else reason,
        "status": VALIDATED_STATUS,
    }

class DetectionService:

    def __init__(self):
        model_dir = Path(__file__).resolve().parents[1] / "vision" / "models"

        pose_model = model_dir / "pose_landmarker_lite.task"
        face_model = model_dir / "face_landmarker.task"

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

    def process_frame(self, frame):
        if frame is None or frame.size == 0:
            raise ValueError("Invalid camera frame")

        # เรียก Detection ของเพื่อนโดยไม่แก้การทำงาน
        pose_points = self.pose_detector.detect(frame)
        face_result = self.face_detector.detect(frame)

        # -------------------------
        # shoulder Tilt
        # -------------------------
        
        shoulder_tilt = None

        if pose_points is not None:
            shoulder_tilt = calculate_shoulder_tilt(
                pose_points.get("left_shoulder"),
                pose_points.get("right_shoulder")
            )

        face_detected = bool(
            face_result is not None
            and face_result.face_landmarks
        )

        frame_height, frame_width = frame.shape[:2]
        face_points = extract_face_points(
            face_result,
            frame_width,
            frame_height,
        )
        orientation = extract_face_orientation(face_result)
        neck_flexion = (
            orientation.get("pitch")
            if isinstance(orientation, dict)
            else None
        )
        eye_measurement = calculate_eye_distance(face_points)
        eye_distance = (
            eye_measurement.get("eye_distance_px")
            if isinstance(eye_measurement, dict)
            else None
        )
           
        # -------------------------
        # Neck Lateral Tilt
        # -------------------------

        neck_lateral_tilt = None

        if pose_points is not None:
            neck_lateral_tilt = calculate_neck_lateral_tilt(
                pose_points.get("left_ear"),
                pose_points.get("right_ear"),
                pose_points.get("left_shoulder"),
                pose_points.get("right_shoulder")
            )


        neck_value = (
            neck_lateral_tilt.get("neck_tilt")
            if isinstance(neck_lateral_tilt, dict)
            else None
        )
        context_valid = bool(pose_points is not None and face_detected)
        features = {
            "shoulder_tilt": _baseline_feature(
                shoulder_tilt, "deg", "SHOULDER_NOT_AVAILABLE"
            ),
            "neck_lateral_tilt": _baseline_feature(
                neck_value, "deg", "NECK_LATERAL_NOT_AVAILABLE"
            ),
            "neck_flexion": _baseline_feature(
                neck_flexion, "deg", "FACE_ORIENTATION_NOT_AVAILABLE"
            ),
            "eye_distance": _baseline_feature(
                eye_distance, "px", "EYE_DISTANCE_NOT_AVAILABLE"
            ),
        }

        return {
            "contract_version": "1.0",
            "timestamp": time.time(),
            "context": {
                "state": "VALID" if context_valid else "INVALID",
                "reason": "OK" if context_valid else "POSE_OR_FACE_MISSING",
                "allow_posture_evaluation": context_valid,
            },
            "features": features,
            "pose_points": pose_points,
            "pose_detected": pose_points is not None,
            "face_detected": face_detected,
            "face_result": face_result,
            "face_points": face_points,
            "shoulder_tilt": shoulder_tilt,
            "neck_lateral_tilt": neck_lateral_tilt,
            "neck_flexion": neck_flexion,
            "eye_distance": eye_distance,
        }

    def close(self):
        self.pose_detector.close()
        self.face_detector.close()
