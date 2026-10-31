import unittest

import cv2
import numpy as np

from app.services.camera_setup.frame_adjustment import (
    adjust_camera_frame,
    mirror_camera_frame,
)


class CameraFrameAdjustmentTests(unittest.TestCase):
    def test_saved_roll_levels_frame_without_changing_dimensions(self):
        level = np.zeros((120, 200, 3), dtype=np.uint8)
        cv2.line(level, (25, 60), (175, 60), (255, 255, 255), 3)
        tilted = cv2.warpAffine(
            level,
            cv2.getRotationMatrix2D((100, 60), -5.0, 1.0),
            (200, 120),
        )

        adjusted = adjust_camera_frame(
            tilted,
            {"status": "VALID", "card_roll_deg": 5.0},
        )

        self.assertEqual(adjusted.shape, tilted.shape)
        points = np.argwhere(adjusted[:, :, 0] > 180)
        slope = np.polyfit(points[:, 1], points[:, 0], 1)[0]
        self.assertAlmostEqual(slope, 0.0, delta=0.02)

    def test_missing_or_invalid_reference_leaves_frame_unchanged(self):
        frame = np.zeros((20, 30, 3), dtype=np.uint8)
        self.assertIs(adjust_camera_frame(frame, None), frame)
        self.assertIs(
            adjust_camera_frame(
                frame,
                {"status": "INVALID", "card_roll_deg": 4.0},
            ),
            frame,
        )

    def test_mirror_camera_frame_reverses_horizontal_direction(self):
        frame = np.array(
            [[[1, 2, 3], [4, 5, 6], [7, 8, 9]]],
            dtype=np.uint8,
        )

        mirrored = mirror_camera_frame(frame)

        np.testing.assert_array_equal(mirrored, frame[:, ::-1])

    def test_mirror_camera_frame_keeps_invalid_frame_unchanged(self):
        self.assertIsNone(mirror_camera_frame(None))
        empty = np.empty((0, 0, 3), dtype=np.uint8)
        self.assertIs(mirror_camera_frame(empty), empty)


if __name__ == "__main__":
    unittest.main()
