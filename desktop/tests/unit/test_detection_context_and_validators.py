import math
import unittest

from app.vision.mediapipe_detection.posture.context_filter import (
    CONTEXT_TRANSITION,
    CONTEXT_UNKNOWN,
    CONTEXT_VALID,
    PostureContextFilter,
)
from app.vision.mediapipe_detection.pose.pose_validator import (
    validate_neck_lateral_tilt,
    validate_pose_feature,
    validate_shoulder_tilt,
    validate_torso_orientation,
)
from app.vision.mediapipe_detection.face.face_feature_validator import (
    validate_face_feature,
)


# ==========================================================
# Test Helpers
# ==========================================================

def pose_point(
    x,
    y,
    *,
    visibility=1.0,
    presence=1.0,
    world_x=0.0,
    world_y=0.0,
    world_z=0.0,
):
    """
    สร้าง Pose Landmark จำลอง

    มีทั้ง:
    - image coordinates
    - visibility / presence
    - world coordinates

    เพื่อให้ใช้ทดสอบได้ทั้ง feature ปกติ
    และ feature ที่ต้องใช้ Pose World Landmark
    """
    return {
        "x": float(x),
        "y": float(y),
        "visibility": float(visibility),
        "presence": float(presence),
        "world_x": float(world_x),
        "world_y": float(world_y),
        "world_z": float(world_z),
    }


def face_point(
    x,
    y,
    *,
    x_norm=0.5,
    y_norm=0.5,
    z=0.0,
):
    """
    สร้าง Face Landmark จำลองตาม contract
    ของ face_feature_validator
    """
    return {
        "x": float(x),
        "y": float(y),
        "x_norm": float(x_norm),
        "y_norm": float(y_norm),
        "z": float(z),
    }


def stable_pose():
    """
    Pose ปกติสำหรับ Context Filter

    Shoulder width = 200 px
    บน frame 640x480

    มากกว่า minimum shoulder width
    ของ Context Filter แน่นอน
    """
    return {
        "nose": pose_point(320, 140),
        "left_ear": pose_point(290, 150),
        "right_ear": pose_point(350, 150),
        "left_shoulder": pose_point(
            220,
            260,
            world_x=-0.2,
        ),
        "right_shoulder": pose_point(
            420,
            260,
            world_x=0.2,
        ),
    }


# ==========================================================
# Context Filter Tests
# ==========================================================

class PostureContextFilterTests(unittest.TestCase):

    def make_filter(self):
        """
        ใช้ stable_time 0.35 วินาทีเหมือน production
        แต่เราควบคุม timestamp เอง
        จึงไม่ต้อง sleep จริง
        """
        return PostureContextFilter(
            stable_time_seconds=0.35,
        )

    def test_missing_pose_is_unknown(self):
        context_filter = self.make_filter()

        result = context_filter.update(
            points=None,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_UNKNOWN,
        )
        self.assertFalse(
            result["allow_posture_evaluation"]
        )
        self.assertEqual(
            result["reason"],
            "pose_not_detected",
        )

    def test_missing_required_shoulder_is_unknown(self):
        context_filter = self.make_filter()

        points = stable_pose()
        del points["left_shoulder"]

        result = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_UNKNOWN,
        )
        self.assertFalse(
            result["allow_posture_evaluation"]
        )
        self.assertEqual(
            result["reason"],
            "missing_left_shoulder",
        )

    def test_low_visibility_is_unknown(self):
        context_filter = self.make_filter()

        points = stable_pose()
        points["left_shoulder"]["visibility"] = 0.2

        result = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_UNKNOWN,
        )
        self.assertFalse(
            result["allow_posture_evaluation"]
        )

        self.assertEqual(
            result["reason"],
            "low_quality_left_shoulder",
        )

    def test_first_valid_frame_is_transition(self):
        context_filter = self.make_filter()

        result = context_filter.update(
            points=stable_pose(),
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_TRANSITION,
        )
        self.assertFalse(
            result["allow_posture_evaluation"]
        )
        self.assertEqual(
            result["reason"],
            "warming_up",
        )

    def test_stable_pose_becomes_valid(self):
        context_filter = self.make_filter()

        points = stable_pose()

        first = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        second = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.1,
        )

        third = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.5,
        )

        self.assertEqual(
            first["state"],
            CONTEXT_TRANSITION,
        )

        self.assertEqual(
            second["state"],
            CONTEXT_TRANSITION,
        )

        self.assertEqual(
            second["reason"],
            "stabilizing",
        )

        self.assertEqual(
            third["state"],
            CONTEXT_VALID,
        )

        self.assertTrue(
            third["allow_posture_evaluation"]
        )

        self.assertEqual(
            third["reason"],
            "stable_upper_body",
        )

    def test_motion_returns_transition(self):
        context_filter = self.make_filter()

        initial = stable_pose()

        context_filter.update(
            points=initial,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        context_filter.update(
            points=initial,
            frame_width=640,
            frame_height=480,
            timestamp=0.1,
        )

        context_filter.update(
            points=initial,
            frame_width=640,
            frame_height=480,
            timestamp=0.5,
        )

        moved = stable_pose()

        # ขยับ landmark หลายจุดมากพอ
        # เพื่อให้เกิน motion threshold
        for name in (
            "nose",
            "left_ear",
            "right_ear",
            "left_shoulder",
            "right_shoulder",
        ):
            moved[name]["x"] += 40.0

        result = context_filter.update(
            points=moved,
            frame_width=640,
            frame_height=480,
            timestamp=0.6,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_TRANSITION,
        )

        self.assertFalse(
            result["allow_posture_evaluation"]
        )

        self.assertEqual(
            result["reason"],
            "posture_transition",
        )

    def test_frame_gap_resets_context(self):
        context_filter = self.make_filter()

        points = stable_pose()

        context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        result = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=1.0,
        )

        self.assertEqual(
            result["state"],
            CONTEXT_TRANSITION,
        )

        self.assertFalse(
            result["allow_posture_evaluation"]
        )

        self.assertEqual(
            result["reason"],
            "frame_gap_reset",
        )

    def test_unknown_resets_previous_stability(self):
        context_filter = self.make_filter()

        points = stable_pose()

        context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.0,
        )

        context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.1,
        )

        valid_result = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.5,
        )

        self.assertEqual(
            valid_result["state"],
            CONTEXT_VALID,
        )

        unknown_result = context_filter.update(
            points=None,
            frame_width=640,
            frame_height=480,
            timestamp=0.6,
        )

        self.assertEqual(
            unknown_result["state"],
            CONTEXT_UNKNOWN,
        )

        recovery_result = context_filter.update(
            points=points,
            frame_width=640,
            frame_height=480,
            timestamp=0.7,
        )

        # หลัง UNKNOWN ต้อง warm-up ใหม่
        # ห้ามกลับ VALID ทันที
        self.assertEqual(
            recovery_result["state"],
            CONTEXT_TRANSITION,
        )

        self.assertEqual(
            recovery_result["reason"],
            "warming_up",
        )


# ==========================================================
# Pose Validator Tests
# ==========================================================

class PoseFeatureValidatorTests(unittest.TestCase):

    def test_shoulder_tilt_accepts_valid_shoulders(self):
        points = stable_pose()

        result = validate_shoulder_tilt(points)

        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "OK")

    def test_shoulder_tilt_does_not_require_nose(self):
        """
        สำคัญมาก:

        Shoulder Tilt ไม่ควร invalid
        เพียงเพราะ Nose หาย
        """
        points = stable_pose()
        del points["nose"]

        result = validate_shoulder_tilt(points)

        self.assertTrue(result["valid"])

    def test_shoulder_tilt_rejects_missing_shoulder(self):
        points = stable_pose()
        del points["right_shoulder"]

        result = validate_shoulder_tilt(points)

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["reason"],
            "LANDMARK_INVALID",
        )
        self.assertIn(
            "right_shoulder",
            result["invalid_points"],
        )

    def test_pose_feature_rejects_low_visibility(self):
        points = stable_pose()

        points["left_shoulder"]["visibility"] = 0.1

        result = validate_shoulder_tilt(points)

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["left_shoulder"],
            "LOW_VISIBILITY",
        )

    def test_pose_feature_rejects_low_presence(self):
        points = stable_pose()

        points["right_shoulder"]["presence"] = 0.1

        result = validate_shoulder_tilt(points)

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["right_shoulder"],
            "LOW_PRESENCE",
        )

    def test_pose_feature_rejects_nan(self):
        points = stable_pose()

        points["left_shoulder"]["x"] = math.nan

        result = validate_shoulder_tilt(points)

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["left_shoulder"],
            "INVALID_X",
        )

    def test_pose_feature_rejects_infinity(self):
        points = stable_pose()

        points["right_shoulder"]["y"] = math.inf

        result = validate_shoulder_tilt(points)

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["right_shoulder"],
            "INVALID_Y",
        )

    def test_neck_lateral_requires_ears(self):
        points = stable_pose()
        del points["left_ear"]

        result = validate_neck_lateral_tilt(
            points
        )

        self.assertFalse(result["valid"])

        self.assertIn(
            "left_ear",
            result["invalid_points"],
        )

    def test_torso_orientation_requires_world_coordinates(self):
        points = stable_pose()

        del points["left_shoulder"]["world_z"]

        result = validate_torso_orientation(
            points
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["left_shoulder"],
            "MISSING_WORLD_Z",
        )

    def test_generic_validator_can_validate_feature_specific_points(self):
        points = stable_pose()

        # Nose ไม่เกี่ยวกับ feature นี้
        del points["nose"]

        result = validate_pose_feature(
            points,
            required_points=(
                "left_shoulder",
                "right_shoulder",
            ),
        )

        self.assertTrue(result["valid"])


# ==========================================================
# Face Feature Validator Tests
# ==========================================================

class FaceFeatureValidatorTests(unittest.TestCase):

    def make_face(self):
        return {
            "left_eye_outer": face_point(
                250,
                200,
                x_norm=0.39,
                y_norm=0.42,
            ),
            "left_eye_inner": face_point(
                280,
                200,
                x_norm=0.44,
                y_norm=0.42,
            ),
            "right_eye_inner": face_point(
                360,
                200,
                x_norm=0.56,
                y_norm=0.42,
            ),
            "right_eye_outer": face_point(
                390,
                200,
                x_norm=0.61,
                y_norm=0.42,
            ),
        }

    def test_valid_face_feature(self):
        points = self.make_face()

        result = validate_face_feature(
            points,
            required_points=(
                "left_eye_outer",
                "left_eye_inner",
                "right_eye_inner",
                "right_eye_outer",
            ),
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "OK")

    def test_missing_face_returns_face_not_found(self):
        result = validate_face_feature(
            None,
            required_points=(
                "left_eye_outer",
            ),
        )

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["reason"],
            "FACE_NOT_FOUND",
        )

    def test_missing_required_face_landmark_is_invalid(self):
        points = self.make_face()
        del points["right_eye_outer"]

        result = validate_face_feature(
            points,
            required_points=(
                "left_eye_outer",
                "right_eye_outer",
            ),
        )

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["reason"],
            "LANDMARK_INVALID",
        )
        self.assertIn(
            "right_eye_outer",
            result["invalid_points"],
        )

    def test_face_feature_rejects_nan(self):
        points = self.make_face()

        points["left_eye_outer"]["x"] = math.nan

        result = validate_face_feature(
            points,
            required_points=(
                "left_eye_outer",
            ),
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["left_eye_outer"],
            "INVALID_X",
        )

    def test_face_feature_rejects_infinity(self):
        points = self.make_face()

        points["left_eye_outer"]["z"] = math.inf

        result = validate_face_feature(
            points,
            required_points=(
                "left_eye_outer",
            ),
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["invalid_reasons"]["left_eye_outer"],
            "INVALID_Z",
        )

    def test_face_feature_only_requires_requested_landmarks(self):
        """
        Feature-specific validation:

        ถ้าเราต้องใช้แค่ left_eye_outer
        การไม่มี landmark อื่นไม่ควรทำให้ invalid
        """
        points = {
            "left_eye_outer": face_point(
                250,
                200,
            )
        }

        result = validate_face_feature(
            points,
            required_points=(
                "left_eye_outer",
            ),
        )

        self.assertTrue(result["valid"])


if __name__ == "__main__":
    unittest.main()