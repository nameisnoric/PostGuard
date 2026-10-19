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

    def test_personal_baseline_validation_metadata_is_accepted(self):
        baseline = PersonalBaselineCreate(**{
            **self.payload(),
            "baseline_status": "SUCCESS",
            "confirmation_status": "CONFIRMED",
            "baseline_sample_count": 60,
            "baseline_duration_seconds": 15.2,
            "baseline_valid_ratio": 0.95,
            "shoulder_angle": -1.25,
            "lateral_tilt_baseline": 2.75,
            "neck_flexion_baseline": 1.5,
            "ipd_baseline": 70.0,
            "shoulder_tilt_sd": 0.5,
            "neck_lateral_tilt_sd": 0.6,
            "neck_flexion_sd": 0.7,
            "eye_distance_sd": 1.2,
        })
        self.assertEqual(baseline.baseline_sample_count, 60)
        self.assertEqual(baseline.confirmation_status, "CONFIRMED")

    def test_invalid_personal_baseline_quality_values_are_rejected(self):
        for change in (
            {"baseline_sample_count": 1},
            {"baseline_duration_seconds": 0},
            {"baseline_valid_ratio": 1.1},
            {"shoulder_tilt_sd": -0.1},
            {"ipd_baseline": 0},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                PersonalBaselineCreate(**{**self.payload(), **change})


if __name__ == "__main__":
    unittest.main()
