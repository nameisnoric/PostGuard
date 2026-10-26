import math
import unittest

from app.vision.mediapipe_detection.posture.relative_neck_rotation import (
    TORSO_MAPPING_K,
    calculate_relative_neck_rotation,
)


class RelativeNeckRotationTests(unittest.TestCase):
    """
    Automated contract and formula tests for
    Relative Neck Rotation.

    These tests do NOT require:
    - Webcam
    - MediaPipe model
    - Personal Baseline capture
    - Risk Pipeline

    They verify only the Relative Neck Rotation metric.
    """

    # ======================================================
    # 1. Neutral
    # ======================================================

    def test_neutral_returns_zero(self):
        result = calculate_relative_neck_rotation(
            head_yaw=0.0,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "OK")

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            0.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["value"],
            0.0,
            places=6,
        )

    # ======================================================
    # 2. Head-only LEFT
    # ======================================================

    def test_head_only_left_remains_strong(self):
        result = calculate_relative_neck_rotation(
            head_yaw=30.0,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["head_delta"],
            30.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["torso_delta"],
            0.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["torso_equivalent"],
            0.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            30.0,
            places=6,
        )

    # ======================================================
    # 3. Head-only RIGHT
    # ======================================================

    def test_head_only_right_remains_strong(self):
        result = calculate_relative_neck_rotation(
            head_yaw=-30.0,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            -30.0,
            places=6,
        )

    # ======================================================
    # 4. Whole-body LEFT suppression
    #
    # With:
    #
    #   head_delta  = +30
    #   torso_delta ≈ -18.28265
    #
    # k * torso_delta ≈ +30
    #
    # Therefore relative neck rotation ≈ 0.
    # ======================================================

    def test_whole_body_left_is_suppressed(self):
        torso_delta = (
            30.0
            /
            TORSO_MAPPING_K
        )

        result = calculate_relative_neck_rotation(
            head_yaw=30.0,
            torso_angle=torso_delta,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["torso_equivalent"],
            30.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            0.0,
            places=6,
        )

    # ======================================================
    # 5. Whole-body RIGHT suppression
    # ======================================================

    def test_whole_body_right_is_suppressed(self):
        torso_delta = (
            -30.0
            /
            TORSO_MAPPING_K
        )

        result = calculate_relative_neck_rotation(
            head_yaw=-30.0,
            torso_angle=torso_delta,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["torso_equivalent"],
            -30.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            0.0,
            places=6,
        )

    # ======================================================
    # 6. Baseline correction
    # ======================================================

    def test_head_baseline_is_subtracted(self):
        result = calculate_relative_neck_rotation(
            head_yaw=15.0,
            torso_angle=0.0,
            head_baseline=5.0,
            torso_baseline=0.0,
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["head_delta"],
            10.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            10.0,
            places=6,
        )

    def test_torso_baseline_is_subtracted(self):
        result = calculate_relative_neck_rotation(
            head_yaw=0.0,
            torso_angle=10.0,
            head_baseline=0.0,
            torso_baseline=5.0,
        )

        expected_torso_delta = 5.0

        expected_torso_equivalent = (
            TORSO_MAPPING_K
            *
            expected_torso_delta
        )

        expected_relative = (
            0.0
            -
            expected_torso_equivalent
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["torso_delta"],
            expected_torso_delta,
            places=6,
        )

        self.assertAlmostEqual(
            result["torso_equivalent"],
            expected_torso_equivalent,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            expected_relative,
            places=6,
        )

    # ======================================================
    # 7. Custom mapping K
    # ======================================================

    def test_custom_mapping_k_is_used(self):
        result = calculate_relative_neck_rotation(
            head_yaw=20.0,
            torso_angle=-10.0,
            head_baseline=0.0,
            torso_baseline=0.0,
            k=-2.0,
        )

        # torso_equivalent
        # = -2 * -10
        # = +20
        #
        # relative
        # = +20 - +20
        # = 0

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["mapping_k"],
            -2.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["torso_equivalent"],
            20.0,
            places=6,
        )

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            0.0,
            places=6,
        )

    # ======================================================
    # 8. Contract
    # ======================================================

    def test_valid_result_contract(self):
        result = calculate_relative_neck_rotation(
            head_yaw=10.0,
            torso_angle=2.0,
            head_baseline=1.0,
            torso_baseline=1.0,
        )

        self.assertTrue(result["valid"])

        expected_keys = {
            "valid",
            "reason",
            "value",
            "relative_neck_rotation",
            "head_delta",
            "torso_delta",
            "torso_equivalent",
            "mapping_k",
            "unit",
            "status",
            "version",
        }

        self.assertTrue(
            expected_keys.issubset(
                result.keys()
            )
        )

        self.assertEqual(
            result["reason"],
            "OK",
        )

        self.assertEqual(
            result["unit"],
            "deg",
        )

        self.assertEqual(
            result["status"],
            "candidate_prototype",
        )

        self.assertEqual(
            result["version"],
            "1.0",
        )

        self.assertEqual(
            result["value"],
            result["relative_neck_rotation"],
        )

    # ======================================================
    # 9. Invalid input
    # ======================================================

    def test_none_input_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw=None,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

        self.assertIsNone(
            result["value"]
        )

        self.assertIsNone(
            result["relative_neck_rotation"]
        )

    def test_nan_input_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw=math.nan,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

        self.assertIsNone(
            result["value"]
        )

    def test_positive_infinity_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw=math.inf,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

    def test_negative_infinity_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw=-math.inf,
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

    def test_invalid_string_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw="invalid",
            torso_angle=0.0,
            head_baseline=0.0,
            torso_baseline=0.0,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

    def test_invalid_k_is_rejected(self):
        result = calculate_relative_neck_rotation(
            head_yaw=10.0,
            torso_angle=5.0,
            head_baseline=0.0,
            torso_baseline=0.0,
            k=math.nan,
        )

        self.assertFalse(result["valid"])

        self.assertEqual(
            result["reason"],
            "INVALID_INPUT",
        )

    # ======================================================
    # 10. Numeric strings
    #
    # Current implementation intentionally accepts values
    # that can safely be converted to float.
    # ======================================================

    def test_numeric_strings_are_supported(self):
        result = calculate_relative_neck_rotation(
            head_yaw="30.0",
            torso_angle="0.0",
            head_baseline="0.0",
            torso_baseline="0.0",
        )

        self.assertTrue(result["valid"])

        self.assertAlmostEqual(
            result["relative_neck_rotation"],
            30.0,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()