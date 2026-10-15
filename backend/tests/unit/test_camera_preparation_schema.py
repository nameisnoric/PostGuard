import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from app.schemas.personal_baseline import PersonalBaselineCreate


class CameraPreparationSchemaTests(unittest.TestCase):
    def payload(self):
        return {
            "camera_id": 1,
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
            "camera_scale_x": 4.1,
            "camera_scale_y": 4.0,
            "camera_scale_avg": 4.05,
            "camera_card_roll": 0.5,
            "camera_horizontal_perspective": 0.02,
            "camera_vertical_perspective": 0.03,
            "camera_calibrated_at": datetime.now(timezone.utc),
        }

    def test_valid_numeric_camera_reference_is_accepted(self):
        baseline = PersonalBaselineCreate(**self.payload())
        self.assertEqual(baseline.camera_frame_width, 1280)
        self.assertEqual(baseline.camera_scale_avg, 4.05)

    def test_invalid_scale_and_perspective_are_rejected(self):
        for change in (
            {"camera_scale_avg": 0},
            {"camera_scale_x": float("nan")},
            {"camera_horizontal_perspective": 1.1},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                PersonalBaselineCreate(**{**self.payload(), **change})


if __name__ == "__main__":
    unittest.main()
