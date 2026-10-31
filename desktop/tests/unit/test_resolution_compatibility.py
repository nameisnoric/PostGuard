import unittest

import numpy as np

from app.vision.camera_setup.resolution_compatibility import (
    RESOLUTION_COMPATIBLE,
    RESOLUTION_MISMATCH,
    RESOLUTION_NOT_EVALUATED,
    evaluate_resolution_compatibility,
    extract_baseline_resolution,
    extract_frame_resolution,
)


class TestBaselineResolution(unittest.TestCase):

    def test_valid_baseline_resolution(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        self.assertEqual(
            extract_baseline_resolution(baseline),
            (1280, 720),
        )

    def test_missing_width_is_invalid(self):
        baseline = {
            "camera_frame_height": 720,
        }

        self.assertIsNone(
            extract_baseline_resolution(baseline)
        )

    def test_missing_height_is_invalid(self):
        baseline = {
            "camera_frame_width": 1280,
        }

        self.assertIsNone(
            extract_baseline_resolution(baseline)
        )

    def test_zero_resolution_is_invalid(self):
        baseline = {
            "camera_frame_width": 0,
            "camera_frame_height": 720,
        }

        self.assertIsNone(
            extract_baseline_resolution(baseline)
        )

    def test_negative_resolution_is_invalid(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": -720,
        }

        self.assertIsNone(
            extract_baseline_resolution(baseline)
        )

    def test_bool_is_not_valid_resolution(self):
        baseline = {
            "camera_frame_width": True,
            "camera_frame_height": 720,
        }

        self.assertIsNone(
            extract_baseline_resolution(baseline)
        )


class TestFrameResolution(unittest.TestCase):

    def test_extract_resolution_from_real_frame_shape(self):
        frame = np.zeros(
            (720, 1280, 3),
            dtype=np.uint8,
        )

        self.assertEqual(
            extract_frame_resolution(frame),
            (1280, 720),
        )

    def test_none_frame_is_invalid(self):
        self.assertIsNone(
            extract_frame_resolution(None)
        )


class TestResolutionCompatibility(unittest.TestCase):

    def test_matching_resolution_is_compatible(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        frame = np.zeros(
            (720, 1280, 3),
            dtype=np.uint8,
        )

        result = evaluate_resolution_compatibility(
            baseline,
            frame,
        )

        self.assertTrue(result["evaluated"])
        self.assertTrue(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_COMPATIBLE,
        )

        self.assertEqual(
            result["expected_width"],
            1280,
        )

        self.assertEqual(
            result["expected_height"],
            720,
        )

        self.assertEqual(
            result["actual_width"],
            1280,
        )

        self.assertEqual(
            result["actual_height"],
            720,
        )

    def test_different_resolution_is_rejected(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        frame = np.zeros(
            (480, 640, 3),
            dtype=np.uint8,
        )

        result = evaluate_resolution_compatibility(
            baseline,
            frame,
        )

        self.assertTrue(result["evaluated"])
        self.assertFalse(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_MISMATCH,
        )

        self.assertEqual(
            result["reason"],
            "resolution_mismatch",
        )

    def test_width_mismatch_is_rejected(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        frame = np.zeros(
            (720, 1920, 3),
            dtype=np.uint8,
        )

        result = evaluate_resolution_compatibility(
            baseline,
            frame,
        )

        self.assertFalse(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_MISMATCH,
        )

    def test_height_mismatch_is_rejected(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        frame = np.zeros(
            (1080, 1280, 3),
            dtype=np.uint8,
        )

        result = evaluate_resolution_compatibility(
            baseline,
            frame,
        )

        self.assertFalse(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_MISMATCH,
        )

    def test_invalid_baseline_fails_closed(self):
        baseline = {
            "camera_frame_width": None,
            "camera_frame_height": None,
        }

        frame = np.zeros(
            (720, 1280, 3),
            dtype=np.uint8,
        )

        result = evaluate_resolution_compatibility(
            baseline,
            frame,
        )

        self.assertFalse(result["evaluated"])
        self.assertFalse(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "invalid_baseline_resolution",
        )

    def test_missing_frame_fails_closed(self):
        baseline = {
            "camera_frame_width": 1280,
            "camera_frame_height": 720,
        }

        result = evaluate_resolution_compatibility(
            baseline,
            None,
        )

        self.assertFalse(result["evaluated"])
        self.assertFalse(result["compatible"])

        self.assertEqual(
            result["status"],
            RESOLUTION_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "invalid_camera_frame",
        )


if __name__ == "__main__":
    unittest.main()