import math
import unittest

from camera_card.session_monitoring.measurement_change_gate import (
    STATUS_CHANGED,
    STATUS_NOT_CONFIGURED,
    STATUS_NOT_EVALUATED,
    STATUS_STABLE,
    derive_threshold_from_samples,
    evaluate_measurement_change,
)


# ============================================================
# Helpers
# ============================================================

def make_feature(
    *,
    delta,
    measurement_valid=True,
    comparison_eligible=True,
):
    """
    สร้างข้อมูล Feature จำลองในรูปแบบเดียวกับที่
    Session Monitoring ส่งให้ Measurement-Change Gate
    """

    return {
        "baseline": 0.0,
        "current": delta,
        "delta": delta,

        "measurement_valid": measurement_valid,

        "baseline_comparison_eligible": (
            comparison_eligible
        ),
    }


def make_snapshot():
    """
    Snapshot จำลองจาก Session Monitoring

    หมายเหตุ:
    eye_distance ยังอยู่ใน snapshot ได้
    เพราะ Session Monitoring ยังสามารถส่งข้อมูลนี้มาได้

    แต่ Measurement-Change Gate v1
    ต้องไม่เอา eye_distance มาประเมิน Posture Change
    """

    return {
        "features": {
            "shoulder_tilt": make_feature(
                delta=1.0,
            ),

            "neck_lateral_tilt": make_feature(
                delta=-2.0,
            ),

            "neck_flexion": make_feature(
                delta=3.0,
            ),

            # Observation only
            # ต้องถูก ignore โดย Posture Change Gate
            "eye_distance": make_feature(
                delta=-10.0,
            ),
        }
    }


def make_config():
    """
    Threshold ที่ได้จาก Final Validation

    Fresh Baseline:
        baseline_id = 21

    Session:
        session_id = 22

    วิธีหา:
        Stable 3 rounds
        → P95 ของแต่ละรอบ
        → ใช้ max(P95) เป็น candidate threshold
    """

    return {
        "contract_version": "1.0",

        "config_version": "1.0",

        "features": {
            "shoulder_tilt": {
                "threshold": 1.153450451105357,
                "unit": "deg",
            },

            "neck_lateral_tilt": {
                "threshold": 2.27582502032104,
                "unit": "deg",
            },

            "neck_flexion": {
                "threshold": 3.5415836524717967,
                "unit": "deg",
            },
        },
    }


# ============================================================
# Measurement Change Gate Tests
# ============================================================

class TestMeasurementChangeGate(
    unittest.TestCase
):

    # --------------------------------------------------------
    # Basic STABLE / CHANGED
    # --------------------------------------------------------

    def test_stable_when_delta_within_threshold(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 1.0

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_STABLE,
        )


    def test_changed_when_delta_above_threshold(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 2.0

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_CHANGED,
        )


    def test_absolute_delta_is_used(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = -5.0

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        row = result[
            "features"
        ][
            "shoulder_tilt"
        ]

        self.assertEqual(
            row[
                "absolute_delta"
            ],
            5.0,
        )

        self.assertEqual(
            row[
                "status"
            ],
            STATUS_CHANGED,
        )


    def test_equal_threshold_is_stable(
        self,
    ):
        snapshot = make_snapshot()

        threshold = (
            make_config()[
                "features"
            ][
                "shoulder_tilt"
            ][
                "threshold"
            ]
        )

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = threshold

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_STABLE,
        )


    # --------------------------------------------------------
    # CHANGED → STABLE
    # --------------------------------------------------------

    def test_changed_can_return_to_stable(
        self,
    ):
        """
        Gate เป็น stateless

        Frame ก่อน:
            delta > threshold
            → CHANGED

        Frame ใหม่:
            delta กลับมาใกล้ baseline
            → STABLE
        """

        changed_snapshot = make_snapshot()

        changed_snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 5.0

        changed_result = (
            evaluate_measurement_change(
                changed_snapshot,
                make_config(),
            )
        )

        self.assertEqual(
            changed_result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_CHANGED,
        )

        stable_snapshot = make_snapshot()

        stable_snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 0.5

        stable_result = (
            evaluate_measurement_change(
                stable_snapshot,
                make_config(),
            )
        )

        self.assertEqual(
            stable_result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_STABLE,
        )


    # --------------------------------------------------------
    # NOT_EVALUATED
    # --------------------------------------------------------

    def test_invalid_measurement_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "measurement_valid"
        ] = False

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_comparison_not_eligible_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "baseline_comparison_eligible"
        ] = False

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_nan_delta_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = math.nan

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_positive_inf_delta_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = math.inf

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_negative_inf_delta_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = -math.inf

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_string_delta_is_not_evaluated(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = "5.0"

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_boolean_delta_is_not_evaluated(
        self,
    ):
        """
        Python bool เป็น subclass ของ int
        ดังนั้นต้องกัน True/False ออกจาก numeric โดยตรง
        """

        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = True

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_EVALUATED,
        )


    # --------------------------------------------------------
    # NOT_CONFIGURED
    # --------------------------------------------------------

    def test_missing_threshold_is_not_configured(
        self,
    ):
        config = make_config()

        del config[
            "features"
        ][
            "shoulder_tilt"
        ]

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_zero_threshold_is_not_configured(
        self,
    ):
        config = make_config()

        config[
            "features"
        ][
            "shoulder_tilt"
        ][
            "threshold"
        ] = 0.0

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_negative_threshold_is_not_configured(
        self,
    ):
        config = make_config()

        config[
            "features"
        ][
            "shoulder_tilt"
        ][
            "threshold"
        ] = -1.0

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_nan_threshold_is_not_configured(
        self,
    ):
        config = make_config()

        config[
            "features"
        ][
            "shoulder_tilt"
        ][
            "threshold"
        ] = math.nan

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_string_threshold_is_not_configured(
        self,
    ):
        config = make_config()

        config[
            "features"
        ][
            "shoulder_tilt"
        ][
            "threshold"
        ] = "1.153"

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_unit_mismatch_is_not_configured(
        self,
    ):
        config = make_config()

        config[
            "features"
        ][
            "shoulder_tilt"
        ][
            "unit"
        ] = "px"

        result = evaluate_measurement_change(
            make_snapshot(),
            config,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    # --------------------------------------------------------
    # Eye Distance exclusion
    # --------------------------------------------------------

    def test_eye_distance_is_not_part_of_posture_gate(
        self,
    ):
        result = evaluate_measurement_change(
            make_snapshot(),
            make_config(),
        )

        self.assertNotIn(
            "eye_distance",
            result[
                "features"
            ],
        )


    def test_only_three_posture_features_are_evaluated(
        self,
    ):
        result = evaluate_measurement_change(
            make_snapshot(),
            make_config(),
        )

        self.assertEqual(
            set(
                result[
                    "features"
                ].keys()
            ),
            {
                "shoulder_tilt",
                "neck_lateral_tilt",
                "neck_flexion",
            },
        )


    # --------------------------------------------------------
    # Overall Status
    # --------------------------------------------------------

    def test_overall_changed_when_any_feature_changed(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 5.0

        snapshot[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "delta"
        ] = 0.5

        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "delta"
        ] = 0.5

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "overall_status"
            ],
            STATUS_CHANGED,
        )


    def test_overall_stable_when_all_features_stable(
        self,
    ):
        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 0.5

        snapshot[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "delta"
        ] = 0.5

        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "delta"
        ] = 0.5

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "overall_status"
            ],
            STATUS_STABLE,
        )


    def test_partial_evaluation_is_not_stable(
        self,
    ):
        """
        ถ้ามี Feature ใดประเมินไม่ได้
        ห้ามสรุป Overall = STABLE
        """

        snapshot = make_snapshot()

        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 0.5

        snapshot[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "delta"
        ] = 0.5

        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "measurement_valid"
        ] = False

        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "baseline_comparison_eligible"
        ] = False

        result = evaluate_measurement_change(
            snapshot,
            make_config(),
        )

        self.assertEqual(
            result[
                "overall_status"
            ],
            STATUS_NOT_EVALUATED,
        )


    def test_not_configured_has_priority_over_not_evaluated(
        self,
    ):
        """
        Priority:
            CHANGED
            > NOT_CONFIGURED
            > NOT_EVALUATED
            > STABLE
        """

        snapshot = make_snapshot()

        config = make_config()

        # Shoulder stable
        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 0.5

        # Neck lateral = NOT_CONFIGURED
        del config[
            "features"
        ][
            "neck_lateral_tilt"
        ]

        # Neck flexion = NOT_EVALUATED
        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "measurement_valid"
        ] = False

        result = evaluate_measurement_change(
            snapshot,
            config,
        )

        self.assertEqual(
            result[
                "overall_status"
            ],
            STATUS_NOT_CONFIGURED,
        )


    def test_changed_has_highest_priority(
        self,
    ):
        snapshot = make_snapshot()

        config = make_config()

        # Shoulder CHANGED
        snapshot[
            "features"
        ][
            "shoulder_tilt"
        ][
            "delta"
        ] = 5.0

        # Neck lateral NOT_CONFIGURED
        del config[
            "features"
        ][
            "neck_lateral_tilt"
        ]

        # Neck flexion NOT_EVALUATED
        snapshot[
            "features"
        ][
            "neck_flexion"
        ][
            "measurement_valid"
        ] = False

        result = evaluate_measurement_change(
            snapshot,
            config,
        )

        self.assertEqual(
            result[
                "overall_status"
            ],
            STATUS_CHANGED,
        )


    # --------------------------------------------------------
    # Legacy Experimental Threshold Derivation
    # --------------------------------------------------------

    def test_threshold_derivation_separable(
        self,
    ):
        """
        Legacy helper เท่านั้น

        ไม่ใช่วิธีที่ใช้สร้าง production/prototype threshold ปัจจุบัน
        """

        stable = [
            0.1,
            0.2,
            0.3,
            0.4,
        ] * 10

        changed = [
            5.0,
            5.5,
            6.0,
            6.5,
        ] * 10

        result = derive_threshold_from_samples(
            stable,
            changed,
            min_samples=30,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "READY",
        )

        self.assertIsNotNone(
            result[
                "threshold"
            ]
        )

        self.assertGreater(
            result[
                "threshold"
            ],
            result[
                "stable_p95_abs_delta"
            ],
        )

        self.assertLess(
            result[
                "threshold"
            ],
            result[
                "changed_p05_abs_delta"
            ],
        )


    def test_threshold_derivation_detects_overlap(
        self,
    ):
        stable = [
            1.0,
            2.0,
            3.0,
            4.0,
        ] * 10

        changed = [
            2.0,
            3.0,
            4.0,
            5.0,
        ] * 10

        result = derive_threshold_from_samples(
            stable,
            changed,
            min_samples=30,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "NOT_SEPARABLE",
        )

        self.assertIsNone(
            result[
                "threshold"
            ]
        )


    def test_threshold_derivation_requires_samples(
        self,
    ):
        result = derive_threshold_from_samples(
            [0.1] * 10,
            [5.0] * 40,
            min_samples=30,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "INSUFFICIENT_STABLE_SAMPLES",
        )


    # --------------------------------------------------------
    # Architecture Boundary
    # --------------------------------------------------------

    def test_risk_stays_not_implemented(
        self,
    ):
        result = evaluate_measurement_change(
            make_snapshot(),
            make_config(),
        )

        self.assertEqual(
            result[
                "risk_score_status"
            ],
            "NOT_IMPLEMENTED",
        )


    def test_alert_stays_not_implemented(
        self,
    ):
        result = evaluate_measurement_change(
            make_snapshot(),
            make_config(),
        )

        self.assertEqual(
            result[
                "alert_status"
            ],
            "NOT_IMPLEMENTED",
        )


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    unittest.main()