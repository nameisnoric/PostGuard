import sys
from pathlib import Path

# หา Project Root ของ PostGuard
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"

# ให้ Desktop สามารถ import โมดูลใน backend ได้
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ใช้ Detection 
from camera_card.mediapipe_detection.pose.pose_detector import PoseDetector
from camera_card.mediapipe_detection.face.face_detector import FaceDetector
from camera_card.mediapipe_detection.posture.posture_features import (
    calculate_shoulder_tilt,
    calculate_neck_lateral_tilt
)

class DetectionService:

    def __init__(self):
        model_dir = BACKEND_DIR / "camera_card" / "models"

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


        return {
            "pose_points": pose_points,
            "face_detected": face_detected,
            "face_result": face_result,
            "shoulder_tilt": shoulder_tilt,
            "neck_lateral_tilt": neck_lateral_tilt
        }

    def close(self):
        self.pose_detector.close()
        self.face_detector.close()
