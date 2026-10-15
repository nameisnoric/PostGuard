import unittest

import cv2
import numpy as np

from app.services.camera_setup.reference_card import (
    CameraCalibrationTracker,
    create_reference,
    guide_bounds,
    validate_card,
)


class CameraCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.bounds = guide_bounds(self.frame)
        center_x, center_y = 640, 360
        width, height = 350, 220
        self.box = np.array(
            [
                [center_x - width // 2, center_y - height // 2],
                [center_x + width // 2, center_y - height // 2],
                [center_x + width // 2, center_y + height // 2],
                [center_x - width // 2, center_y + height // 2],
            ],
            dtype=np.float32,
        )
        self.card = {
            "box": self.box,
            "ratio": width / height,
            "fill": (width * height) / (
                (self.bounds[2] - self.bounds[0])
                * (self.bounds[3] - self.bounds[1])
            ),
            "is_card": True,
        }

    def test_valid_card_creates_serializable_numeric_reference(self):
        validation = validate_card(self.card, self.bounds)
        reference = create_reference(self.frame, self.card, validation)

        self.assertTrue(validation["valid"])
        self.assertEqual(reference["status"], "VALID")
        self.assertEqual(reference["frame_width"], 1280)
        self.assertGreater(reference["scale_avg"], 0)
        self.assertNotIn("card_box", reference)
        self.assertNotIn("image", reference)

    def test_tracker_requires_consecutive_stable_frames(self):
        cv2.fillConvexPoly(self.frame, self.box.astype(np.int32), (255, 255, 255))
        tracker = CameraCalibrationTracker(stable_frames=2)

        first = tracker.process(self.frame)
        second = tracker.process(self.frame)

        self.assertEqual(first["stable_count"], 1)
        self.assertIsNone(first["reference"])
        self.assertEqual(second["stable_count"], 2)
        self.assertEqual(second["reference"]["status"], "VALID")
        self.assertTrue(np.any(second["display_frame"][10:80, -180:] != 0))

    def test_missing_card_resets_stability(self):
        tracker = CameraCalibrationTracker(stable_frames=2)
        tracker.stable_count = 1
        result = tracker.process(self.frame)
        self.assertEqual(result["stable_count"], 0)
        self.assertIsNone(result["reference"])


if __name__ == "__main__":
    unittest.main()
