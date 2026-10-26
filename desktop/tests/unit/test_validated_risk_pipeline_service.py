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

    def test_single_factor_moderate_requires_first_alert_confirmation(
        self,
    ):
        """
        One factor:
            < 60 seconds -> LOW

        At 60 seconds:
            MODERATE
            Risk Event starts

        User-facing FIRST notification:
            waits another 5 seconds by UX policy.
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
            first["risk"]["risk_level"],
            "LOW",
        )

        self.assertEqual(
            first["risk_event"][
                "event_action"
            ],
            "NONE",
        )

        moderate_start = (
            service.process_detection(
                detection,
                baseline,
                now=160.0,
            )
        )

        self.assertEqual(
            moderate_start[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            moderate_start[
                "risk_event"
            ][
                "event_action"
            ],
            "STARTED",
        )

        # MODERATE first alert is intentionally delayed.
        self.assertFalse(
            moderate_start[
                "alert_policy"
            ][
                "should_notify"
            ]
        )

        confirmed = (
            service.process_detection(
                detection,
                baseline,
                now=165.0,
            )
        )

        self.assertEqual(
            confirmed[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertTrue(
            confirmed[
                "alert_policy"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            confirmed[
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

    def test_neutral_posture_exposes_modified_rula_score(
        self,
    ):
        service = (
            ValidatedRiskPipelineService()
        )

        result = service.process_detection(
            build_detection(
                shoulder_tilt=0.0,
                neck_lateral_tilt=0.0,
                neck_flexion=0.0,
            ),
            build_baseline(),
            now=0.0,
        )

        score = (
            result[
                "posture_score"
            ]
        )

        self.assertEqual(
            score[
                "status"
            ],
            "COMPLETE",
        )

        self.assertEqual(
            score[
                "modified_rula_score"
            ],
            1,
        )

        self.assertEqual(
            score[
                "postguard_risk_score"
            ],
            0,
        )


    def test_posture_score_changes_with_detected_posture(
        self,
    ):
        service = (
            ValidatedRiskPipelineService()
        )

        result = service.process_detection(
            build_detection(
                shoulder_tilt=6.0,
                neck_lateral_tilt=8.0,
                neck_flexion=25.0,
            ),
            build_baseline(),
            now=0.0,
        )

        score = (
            result[
                "posture_score"
            ]
        )

        # Neck >20° = 3
        # neck side bending = +1
        # shoulder asymmetry = +1
        # duration at first frame = +0
        #
        # total = 5
        self.assertEqual(
            score[
                "modified_rula_score"
            ],
            5,
        )

        self.assertEqual(
            score[
                "postguard_risk_score"
            ],
            67,
        )


    def test_sustained_posture_increases_modified_rula(
        self,
    ):
        service = (
            ValidatedRiskPipelineService()
        )

        detection = build_detection(
            shoulder_tilt=6.0,
            neck_lateral_tilt=0.0,
            neck_flexion=0.0,
        )

        baseline = build_baseline()

        first = (
            service.process_detection(
                detection,
                baseline,
                now=100.0,
            )
        )

        self.assertEqual(
            first[
                "posture_score"
            ][
                "modified_rula_score"
            ],
            2,
        )

        after_sixty = (
            service.process_detection(
                detection,
                baseline,
                now=160.0,
            )
        )

        # Neck base 1
        # Shoulder asymmetry +1
        # Sustained >=60 sec +1
        #
        # total = 3
        self.assertEqual(
            after_sixty[
                "posture_score"
            ][
                "modified_rula_score"
            ],
            3,
        )

        self.assertEqual(
            after_sixty[
                "posture_score"
            ][
                "postguard_risk_score"
            ],
            33,
        )


if __name__ == "__main__":
    unittest.main()