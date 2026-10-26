import math
import unittest

from app.vision.mediapipe_detection.posture.relative_screen_distance import (
    DIRECTION_BASELINE,
    DIRECTION_CLOSER,
    DIRECTION_FARTHER,
    STATUS_EVALUATED,
    STATUS_NOT_EVALUATED,
    calculate_relative_screen_distance,
    evaluate_relative_screen_distance,
    extract_eye_distance_baseline,
)


def make_detection(
    value=100.0,
    *,
    valid=True,
    unit="px",
    reason="OK",
):
    return {
        "contract_version": "1.0",

        "features": {
            "eye_distance": {
                "valid": valid,
                "value": value,
                "unit": unit,
                "reason": reason,
                "status": "validated_prototype",
            },
        },
    }


class RelativeScreenDistanceTests(
    unittest.TestCase
):

    # ======================================================
    # Core Calculation
    # ======================================================

    def test_same_as_baseline_returns_ratio_one(
        self,
    ):
        result = (
            calculate_relative_screen_distance(
                current_eye_distance_px=100.0,
                baseline_eye_distance_px=100.0,
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_EVALUATED,
        )

        self.assertAlmostEqual(
            result["relative_ratio"],
            1.0,
        )

        self.assertAlmostEqual(
            result["relative_change"],
            0.0,
        )

        self.assertAlmostEqual(
            result["percent_change"],
            0.0,
        )

        self.assertEqual(
            result["direction"],
            DIRECTION_BASELINE,
        )


    def test_larger_eye_distance_is_closer(
        self,
    ):
        result = (
            calculate_relative_screen_distance(
                current_eye_distance_px=130.0,
                baseline_eye_distance_px=100.0,
            )
        )

        self.assertAlmostEqual(
            result["relative_ratio"],
            1.30,
        )

        self.assertAlmostEqual(
            result["percent_change"],
            30.0,
        )

        self.assertEqual(
            result["direction"],
            DIRECTION_CLOSER,
        )


    def test_smaller_eye_distance_is_farther(
        self,
    ):
        result = (
            calculate_relative_screen_distance(
                current_eye_distance_px=75.0,
                baseline_eye_distance_px=100.0,
            )
        )

        self.assertAlmostEqual(
            result["relative_ratio"],
            0.75,
        )

        self.assertAlmostEqual(
            result["percent_change"],
            -25.0,
        )

        self.assertEqual(
            result["direction"],
            DIRECTION_FARTHER,
        )


    # ======================================================
    # No Risk Threshold
    # ======================================================

    def test_calculation_does_not_classify_too_close(
        self,
    ):
        result = (
            calculate_relative_screen_distance(
                current_eye_distance_px=200.0,
                baseline_eye_distance_px=100.0,
            )
        )

        self.assertEqual(
            result["direction"],
            DIRECTION_CLOSER,
        )

        self.assertIsNone(
            result["is_too_close"]
        )

        self.assertIsNone(
            result["is_too_far"]
        )

        self.assertFalse(
            result["threshold_applied"]
        )

        self.assertFalse(
            result[
                "semantics"
            ][
                "risk_evaluation"
            ]
        )


    # ======================================================
    # Baseline Compatibility
    # ======================================================

    def test_reads_current_backend_ipd_baseline(
        self,
    ):
        (
            value,
            source,
            reason,
        ) = extract_eye_distance_baseline(
            {
                "ipd_baseline":
                    120.0,
            }
        )

        self.assertEqual(
            value,
            120.0,
        )

        self.assertEqual(
            source,
            "ipd_baseline",
        )

        self.assertEqual(
            reason,
            "OK",
        )


    def test_reads_personal_baseline_collector_format(
        self,
    ):
        (
            value,
            source,
            reason,
        ) = extract_eye_distance_baseline(
            {
                "eye_distance":
                    115.0,
            }
        )

        self.assertEqual(
            value,
            115.0,
        )

        self.assertEqual(
            source,
            "eye_distance",
        )

        self.assertEqual(
            reason,
            "OK",
        )


    def test_new_explicit_field_has_priority(
        self,
    ):
        (
            value,
            source,
            reason,
        ) = extract_eye_distance_baseline(
            {
                "eye_distance_baseline_px":
                    125.0,

                "ipd_baseline":
                    100.0,

                "eye_distance":
                    90.0,
            }
        )

        self.assertEqual(
            value,
            125.0,
        )

        self.assertEqual(
            source,
            "eye_distance_baseline_px",
        )

        self.assertEqual(
            reason,
            "OK",
        )


    # ======================================================
    # Detection Integration
    # ======================================================

    def test_evaluate_detection_and_baseline(
        self,
    ):
        result = (
            evaluate_relative_screen_distance(
                make_detection(
                    150.0
                ),

                {
                    "ipd_baseline":
                        100.0,
                },
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "OK",
        )

        self.assertAlmostEqual(
            result["relative_ratio"],
            1.5,
        )

        self.assertAlmostEqual(
            result["percent_change"],
            50.0,
        )

        self.assertEqual(
            result["direction"],
            DIRECTION_CLOSER,
        )

        self.assertEqual(
            result["baseline_source"],
            "ipd_baseline",
        )


    # ======================================================
    # Invalid Detection
    # ======================================================

    def test_invalid_detection_is_not_evaluated(
        self,
    ):
        result = (
            evaluate_relative_screen_distance(
                make_detection(
                    None,
                    valid=False,
                    reason="EYE_DISTANCE_NOT_AVAILABLE",
                ),

                {
                    "ipd_baseline":
                        100.0,
                },
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "EYE_DISTANCE_NOT_AVAILABLE",
        )

        self.assertIsNone(
            result["relative_ratio"]
        )


    def test_wrong_unit_is_not_evaluated(
        self,
    ):
        result = (
            evaluate_relative_screen_distance(
                make_detection(
                    100.0,
                    unit="cm",
                ),

                {
                    "ipd_baseline":
                        100.0,
                },
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "INVALID_EYE_DISTANCE_UNIT",
        )


    # ======================================================
    # Missing Baseline
    # ======================================================

    def test_missing_baseline_is_not_evaluated(
        self,
    ):
        result = (
            evaluate_relative_screen_distance(
                make_detection(
                    100.0
                ),
                None,
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "BASELINE_MISSING",
        )

        self.assertIsNone(
            result["relative_ratio"]
        )


    def test_missing_eye_baseline_is_not_evaluated(
        self,
    ):
        result = (
            evaluate_relative_screen_distance(
                make_detection(
                    100.0
                ),

                {
                    "shoulder_angle":
                        2.0,
                },
            )
        )

        self.assertEqual(
            result["status"],
            STATUS_NOT_EVALUATED,
        )

        self.assertEqual(
            result["reason"],
            "EYE_DISTANCE_BASELINE_MISSING",
        )


    # ======================================================
    # Invalid Numeric Values
    # ======================================================

    def test_zero_baseline_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            calculate_relative_screen_distance(
                current_eye_distance_px=100.0,
                baseline_eye_distance_px=0.0,
            )


    def test_negative_current_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            calculate_relative_screen_distance(
                current_eye_distance_px=-10.0,
                baseline_eye_distance_px=100.0,
            )


    def test_nan_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            calculate_relative_screen_distance(
                current_eye_distance_px=math.nan,
                baseline_eye_distance_px=100.0,
            )


    def test_infinity_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            calculate_relative_screen_distance(
                current_eye_distance_px=math.inf,
                baseline_eye_distance_px=100.0,
            )


    def test_bool_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            calculate_relative_screen_distance(
                current_eye_distance_px=True,
                baseline_eye_distance_px=100.0,
            )


if __name__ == "__main__":
    unittest.main()