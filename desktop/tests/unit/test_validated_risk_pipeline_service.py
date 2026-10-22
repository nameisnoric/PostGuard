import unittest

from app.services.baseline_comparison_service import (
    compare_detection_to_baseline,
)

from app.services.validated_risk_pipeline_service import (
    ValidatedRiskPipelineService,
)


def build_detection(
    *,
    shoulder_tilt=0.0,
    neck_lateral_tilt=0.0,
    neck_flexion=0.0,
):
    return {
        "contract_version": "1.0",
        "timestamp": 0.0,
        "context": {
            "state": "VALID",
            "reason": "OK",
            "allow_posture_evaluation": True,
        },
        "features": {
            "shoulder_tilt": {
                "valid": True,
                "value": shoulder_tilt,
                "unit": "deg",
                "reason": "OK",
                "status": "VALID",
            },
            "neck_lateral_tilt": {
                "valid": True,
                "value": neck_lateral_tilt,
                "unit": "deg",
                "reason": "OK",
                "status": "VALID",
            },
            "neck_flexion": {
                "valid": True,
                "value": neck_flexion,
                "unit": "deg",
                "reason": "OK",
                "status": "VALID",
            },
        },
    }


def build_baseline(
    *,
    shoulder_angle=0.0,
    lateral_tilt_baseline=0.0,
    neck_flexion_baseline=0.0,
):
    return {
        "shoulder_angle": shoulder_angle,
        "lateral_tilt_baseline": (
            lateral_tilt_baseline
        ),
        "neck_flexion_baseline": (
            neck_flexion_baseline
        ),
        "shoulder_tilt_sd": 0.5,
        "neck_lateral_tilt_sd": 0.5,
        "neck_flexion_sd": 0.5,
    }


class ValidatedRiskPipelineServiceTests(
    unittest.TestCase
):

    def test_baseline_comparison_does_not_modify_assessment_value(
        self,
    ):
        """
        Baseline comparison and Current Posture Assessment are
        separate layers.

        Current = 7 degrees
        Baseline = 2 degrees
        Delta = 5 degrees

        Assessment must still evaluate CURRENT = 7,
        not compensated 5.
        """

        service = (
            ValidatedRiskPipelineService()
        )

        detection = build_detection(
            shoulder_tilt=7.0,
        )

        baseline = build_baseline(
            shoulder_angle=2.0,
        )

        result = service.process_detection(
            detection,
            baseline,
            now=0.0,
        )

        comparison = (
            result[
                "baseline_comparison"
            ][
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            comparison["current"],
            7.0,
        )

        self.assertEqual(
            comparison["baseline"],
            2.0,
        )

        self.assertEqual(
            comparison["delta"],
            5.0,
        )

        assessment_feature = (
            result[
                "assessment"
            ][
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            assessment_feature["current"],
            7.0,
        )

        self.assertEqual(
            assessment_feature["status"],
            "RIGHT_SHOULDER_HIGH",
        )

    def test_gate_is_not_configured_without_validated_rules(
        self,
    ):
        """
        We intentionally do not invent production thresholds
        for Measurement-Change Gate.
        """

        result = compare_detection_to_baseline(
            build_detection(
                shoulder_tilt=10.0,
            ),
            build_baseline(
                shoulder_angle=0.0,
            ),
        )

        feature = (
            result[
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            feature[
                "gate"
            ][
                "state"
            ],
            "NOT_CONFIGURED",
        )

        self.assertIsNone(
            feature[
                "gate"
            ][
                "changed"
            ]
        )

        self.assertEqual(
            result[
                "gate"
            ][
                "state"
            ],
            "NOT_CONFIGURED",
        )

    def test_explicit_test_gate_rule_can_classify_change(
        self,
    ):
        """
        Explicit rules are supported for future validation tests.

        This 3-degree threshold is TEST DATA only.
        It is not a production PostGuard threshold.
        """

        gate_rules = {
            "features": {
                "shoulder_tilt": {
                    "change_threshold_deg": 3.0,
                },
            },
        }

        result = compare_detection_to_baseline(
            build_detection(
                shoulder_tilt=5.0,
            ),
            build_baseline(
                shoulder_angle=1.0,
            ),
            gate_rules=gate_rules,
        )

        feature = (
            result[
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            feature["delta"],
            4.0,
        )

        self.assertEqual(
            feature[
                "gate"
            ][
                "state"
            ],
            "CHANGED",
        )

        self.assertTrue(
            feature[
                "gate"
            ][
                "changed"
            ]
        )

    def test_missing_baseline_does_not_invalidate_current_posture(
        self,
    ):
        """
        Missing baseline comparison data must not turn a valid
        current posture measurement into unavailable posture.
        """

        service = (
            ValidatedRiskPipelineService()
        )

        detection = build_detection(
            shoulder_tilt=6.0,
            neck_lateral_tilt=0.0,
            neck_flexion=0.0,
        )

        baseline = {
            "shoulder_angle": 0.0,
            "lateral_tilt_baseline": 0.0,

            # intentionally missing:
            # neck_flexion_baseline
        }

        result = service.process_detection(
            detection,
            baseline,
            now=0.0,
        )

        comparison = (
            result[
                "baseline_comparison"
            ][
                "features"
            ][
                "neck_flexion"
            ]
        )

        self.assertEqual(
            comparison["status"],
            "NOT_EVALUATED",
        )

        # Current posture remains valid because the current
        # Detection measurement itself is still valid.
        self.assertEqual(
            result[
                "assessment"
            ][
                "status"
            ],
            "COMPLETE",
        )

    def test_single_factor_becomes_moderate_after_60_seconds(
        self,
    ):
        """
        One continuously active posture factor starts as LOW.

        After 60 seconds:
        LOW -> MODERATE
        Risk Event -> STARTED
        Alert Policy -> FIRST
        """

        service = (
            ValidatedRiskPipelineService()
        )

        detection = build_detection(
            shoulder_tilt=5.0,
            neck_lateral_tilt=0.0,
            neck_flexion=0.0,
        )

        baseline = build_baseline()

        first = service.process_detection(
            detection,
            baseline,
            now=100.0,
        )

        self.assertEqual(
            first[
                "risk"
            ][
                "risk_level"
            ],
            "LOW",
        )

        self.assertEqual(
            first[
                "risk_event"
            ][
                "event_action"
            ],
            "NONE",
        )

        second = service.process_detection(
            detection,
            baseline,
            now=160.0,
        )

        self.assertEqual(
            second[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        # Risk Event Contract 1.0 uses event_action,
        # not action.
        self.assertEqual(
            second[
                "risk_event"
            ][
                "event_action"
            ],
            "STARTED",
        )

        self.assertTrue(
            second[
                "risk_event"
            ][
                "event_active"
            ]
        )

        self.assertIsNotNone(
            second[
                "risk_event"
            ][
                "event"
            ]
        )

        self.assertTrue(
            second[
                "alert_policy"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            second[
                "alert_policy"
            ][
                "alert_type"
            ],
            "FIRST",
        )

    def test_reset_breaks_temporal_continuity(
        self,
    ):
        """
        Reset must prevent posture duration from continuing
        across Pause/Resume or Session boundaries.
        """

        service = (
            ValidatedRiskPipelineService()
        )

        detection = build_detection(
            shoulder_tilt=5.0,
        )

        baseline = build_baseline()

        service.process_detection(
            detection,
            baseline,
            now=100.0,
        )

        before_reset = (
            service.process_detection(
                detection,
                baseline,
                now=150.0,
            )
        )

        self.assertEqual(
            before_reset[
                "risk"
            ][
                "risk_level"
            ],
            "LOW",
        )

        service.reset()

        result = service.process_detection(
            detection,
            baseline,
            now=160.0,
        )

        self.assertEqual(
            result[
                "risk"
            ][
                "risk_level"
            ],
            "LOW",
        )

        # New tracker = no existing Risk Event.
        self.assertEqual(
            result[
                "risk_event"
            ][
                "event_action"
            ],
            "NONE",
        )

        self.assertFalse(
            result[
                "risk_event"
            ][
                "event_active"
            ]
        )

        self.assertIsNone(
            result[
                "risk_event"
            ][
                "event"
            ]
        )

    def test_score_is_explicitly_not_implemented_yet(
        self,
    ):
        """
        The integration contract reserves a place for the future
        PostGuard Modified RULA score.

        It must remain explicitly unavailable until that score
        module is designed and validated.
        """

        service = (
            ValidatedRiskPipelineService()
        )

        result = service.process_detection(
            build_detection(),
            build_baseline(),
            now=0.0,
        )

        self.assertEqual(
            result[
                "posture_score"
            ][
                "status"
            ],
            "NOT_IMPLEMENTED",
        )

        self.assertIsNone(
            result[
                "posture_score"
            ][
                "modified_rula_score"
            ]
        )


if __name__ == "__main__":
    unittest.main()