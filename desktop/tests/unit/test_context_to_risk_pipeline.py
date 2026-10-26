import unittest

from app.services.validated_risk_pipeline_service import (
    ValidatedRiskPipelineService,
)


# ============================================================
# Detection Contract helpers
# ============================================================

def make_feature(
    value,
    *,
    unit="deg",
    valid=True,
    reason="OK",
    status="validated_prototype",
):
    """
    Build one Detection Contract feature.

    This intentionally mirrors Detection Contract v1.0 rather
    than mocking Assessment / Temporal / Risk individually.

    Therefore the test exercises the real pipeline boundary:

        Detection
            â†“
        Assessment
            â†“
        Temporal
            â†“
        Risk
            â†“
        Risk Event
    """

    return {
        "value": value,
        "unit": unit,
        "valid": valid,
        "reason": reason,
        "status": status,
    }


def make_detection(
    *,
    context_state="VALID",
    allow_posture_evaluation=True,
    shoulder_tilt=0.0,
    neck_lateral_tilt=0.0,
    neck_flexion=0.0,
):
    """
    Build a minimal Detection Contract v1.0 result.

    eye_distance is included for compatibility with the current
    Detection Contract, but it is intentionally NOT part of
    posture-risk evaluation.
    """

    return {
        "contract_version": "1.0",

        "context": {
            "state": context_state,
            "reason": (
                "stable_upper_body"
                if context_state == "VALID"
                else "posture_context_not_evaluable"
            ),
            "allow_posture_evaluation": (
                allow_posture_evaluation
            ),
            "stable_seconds": (
                1.0
                if context_state == "VALID"
                else 0.0
            ),
        },

        "features": {
            "shoulder_tilt": make_feature(
                shoulder_tilt,
            ),

            "neck_lateral_tilt": make_feature(
                neck_lateral_tilt,
            ),

            "neck_flexion": make_feature(
                neck_flexion,
                status="experimental",
            ),

            "eye_distance": make_feature(
                70.0,
                unit="px",
            ),
        },

        # ----------------------------------------------------
        # Legacy compatibility keys
        # ----------------------------------------------------

        "shoulder_tilt": shoulder_tilt,

        "neck_lateral_tilt": {
            "neck_tilt": neck_lateral_tilt,
        },

        "neck_flexion": neck_flexion,

        "eye_distance": 70.0,
    }


# ============================================================
# Assertions
# ============================================================

def assert_temporal_not_evaluated(
    test_case,
    temporal_result,
):
    """
    Every posture feature must stop temporal continuity when
    Current Posture Assessment cannot evaluate the frame.
    """

    test_case.assertEqual(
        temporal_result["status"],
        "NOT_EVALUATED",
    )

    for feature_name in (
        "shoulder_tilt",
        "neck_lateral_tilt",
        "neck_flexion",
    ):
        feature = temporal_result["features"][
            feature_name
        ]

        test_case.assertEqual(
            feature["state"],
            "NOT_EVALUATED",
            msg=(
                f"{feature_name} should be "
                f"NOT_EVALUATED: {feature}"
            ),
        )

        test_case.assertFalse(
            feature["evaluable"],
            msg=(
                f"{feature_name} unexpectedly "
                f"evaluable: {feature}"
            ),
        )

        test_case.assertFalse(
            feature["active"],
            msg=(
                f"{feature_name} unexpectedly "
                f"active: {feature}"
            ),
        )

        test_case.assertIsNone(
            feature["continuous_seconds"],
            msg=(
                f"{feature_name} invented "
                f"continuous duration: {feature}"
            ),
        )


# ============================================================
# STEP 2D Integration Tests
# ============================================================

class ContextToRiskPipelineTests(
    unittest.TestCase
):

    def setUp(self):
        self.service = (
            ValidatedRiskPipelineService()
        )

    # --------------------------------------------------------
    # TRANSITION
    # --------------------------------------------------------

    def test_transition_becomes_data_gap_not_safe_posture(
        self,
    ):
        """
        TRANSITION means:

            posture cannot currently be evaluated

        It must NOT mean:

            safe
            neutral
            LOW
            NONE
        """

        detection = make_detection(
            context_state="TRANSITION",
            allow_posture_evaluation=False,
        )

        result = self.service.process_detection(
            detection,
            baseline_data=None,
            now=100.0,
        )

        assessment = result["assessment"]
        temporal = result["temporal"]
        risk = result["risk"]
        risk_event = result["risk_event"]

        # ----------------------------------------------------
        # Assessment
        # ----------------------------------------------------

        self.assertFalse(
            assessment["evaluable"]
        )

        # ----------------------------------------------------
        # Temporal
        # ----------------------------------------------------

        assert_temporal_not_evaluated(
            self,
            temporal,
        )

        # ----------------------------------------------------
        # Risk
        #
        # Missing/unevaluable posture must never become a
        # fake evaluated safe Risk result.
        # ----------------------------------------------------

        self.assertNotEqual(
            risk["status"],
            "EVALUATED",
        )

        self.assertIsNone(
            risk["risk_level"]
        )

        # ----------------------------------------------------
        # Risk Event
        # ----------------------------------------------------

        self.assertEqual(
            risk_event["event_action"],
            "DATA_GAP",
        )

        self.assertFalse(
            risk_event["event_active"],
        )

        self.assertIsNone(
            risk_event["event"],
        )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    def test_unknown_becomes_data_gap_not_safe_posture(
        self,
    ):
        """
        UNKNOWN follows the same conservative rule as
        TRANSITION.

        Missing/invalid context is not evidence that posture
        is safe.
        """

        detection = make_detection(
            context_state="UNKNOWN",
            allow_posture_evaluation=False,
        )

        result = self.service.process_detection(
            detection,
            baseline_data=None,
            now=100.0,
        )

        assessment = result["assessment"]
        temporal = result["temporal"]
        risk = result["risk"]
        risk_event = result["risk_event"]

        self.assertFalse(
            assessment["evaluable"]
        )

        assert_temporal_not_evaluated(
            self,
            temporal,
        )

        self.assertNotEqual(
            risk["status"],
            "EVALUATED",
        )

        self.assertIsNone(
            risk["risk_level"]
        )

        self.assertEqual(
            risk_event["event_action"],
            "DATA_GAP",
        )

        self.assertFalse(
            risk_event["event_active"],
        )

    # --------------------------------------------------------
    # Context / measurement separation
    # --------------------------------------------------------

    def test_context_gap_does_not_require_detection_values_to_disappear(
        self,
    ):
        """
        Important architectural rule:

        Detection may still contain measurable feature values
        while posture Context is TRANSITION.

        Context controls whether posture may advance through
        Assessment / Temporal / Risk.

        It does NOT require Detection to erase measurements.
        """

        detection = make_detection(
            context_state="TRANSITION",
            allow_posture_evaluation=False,
            shoulder_tilt=12.0,
            neck_lateral_tilt=15.0,
            neck_flexion=20.0,
        )

        # Detection still measured the values.
        self.assertTrue(
            detection["features"][
                "shoulder_tilt"
            ]["valid"]
        )

        self.assertEqual(
            detection["features"][
                "shoulder_tilt"
            ]["value"],
            12.0,
        )

        result = self.service.process_detection(
            detection,
            baseline_data=None,
            now=100.0,
        )

        # But posture evaluation is blocked.
        self.assertFalse(
            result["assessment"]["evaluable"]
        )

        assert_temporal_not_evaluated(
            self,
            result["temporal"],
        )

        self.assertNotEqual(
            result["risk"]["status"],
            "EVALUATED",
        )

        self.assertEqual(
            result["risk_event"]["event_action"],
            "DATA_GAP",
        )

    # --------------------------------------------------------
    # Temporal continuity
    # --------------------------------------------------------

    def test_data_gap_resets_posture_continuity(
        self,
    ):
        """
        Prove the most important Temporal rule.

        Active posture:
            t = 100

        Same active posture:
            t = 110

        Therefore continuous exposure may reach ~10 sec.

        Then:
            t = 111 -> TRANSITION / DATA GAP

        Then same posture returns:
            t = 120

        Duration must restart.

        It must NOT continue from the old 100-second start.
        """

        active_detection = make_detection(
            context_state="VALID",
            allow_posture_evaluation=True,

            # Deliberately large values so at least posture
            # factors are produced by Current Assessment.
            shoulder_tilt=20.0,
            neck_lateral_tilt=20.0,
            neck_flexion=25.0,
        )

        # First active sample.
        first = self.service.process_detection(
            active_detection,
            baseline_data=None,
            now=100.0,
        )

        # Same posture 10 seconds later.
        before_gap = (
            self.service.process_detection(
                active_detection,
                baseline_data=None,
                now=110.0,
            )
        )

        active_before_gap = []

        for feature_name, feature in (
            before_gap["temporal"][
                "features"
            ].items()
        ):
            if (
                feature.get("active") is True
                and
                feature.get(
                    "continuous_seconds"
                )
                is not None
            ):
                active_before_gap.append(
                    feature_name
                )

        self.assertTrue(
            active_before_gap,
            msg=(
                "Test setup did not produce any "
                "active posture factor. "
                f"Temporal result: "
                f"{before_gap['temporal']}"
            ),
        )

        # Context becomes unusable.
        gap_detection = make_detection(
            context_state="TRANSITION",
            allow_posture_evaluation=False,
            shoulder_tilt=20.0,
            neck_lateral_tilt=20.0,
            neck_flexion=25.0,
        )

        gap = self.service.process_detection(
            gap_detection,
            baseline_data=None,
            now=111.0,
        )

        assert_temporal_not_evaluated(
            self,
            gap["temporal"],
        )

        # Same posture returns later.
        after_gap = (
            self.service.process_detection(
                active_detection,
                baseline_data=None,
                now=120.0,
            )
        )

        for feature_name in active_before_gap:
            feature = (
                after_gap["temporal"][
                    "features"
                ][feature_name]
            )

            # If the factor is still active after returning,
            # it must be a NEW continuous interval.
            if feature.get("active") is True:

                self.assertAlmostEqual(
                    feature[
                        "continuous_seconds"
                    ],
                    0.0,
                    places=6,
                    msg=(
                        f"{feature_name} incorrectly "
                        "continued duration across "
                        "DATA_GAP: "
                        f"{feature}"
                    ),
                )

    # --------------------------------------------------------
    # Active Risk Event survives data gap
    # --------------------------------------------------------

    def test_active_risk_event_survives_data_gap(
        self,
    ):
        """
        This test proves the Risk Event rule directly at the
        integrated service boundary.

        We first feed risky posture long enough for the real
        pipeline to create an Event.

        Then Context becomes UNKNOWN.

        Expected:

            Risk unavailable
                â†“
            DATA_GAP
                â†“
            existing Risk Event remains active
        """

        risky_detection = make_detection(
            context_state="VALID",
            allow_posture_evaluation=True,
            shoulder_tilt=25.0,
            neck_lateral_tilt=25.0,
            neck_flexion=30.0,
        )

        event_result = None

        # ----------------------------------------------------
        # Feed repeated valid risky samples.
        #
        # We deliberately do not assume the exact duration
        # threshold here. The loop searches for the first real
        # event produced by the current validated pipeline.
        # ----------------------------------------------------

        for second in range(0, 121, 5):
            current = (
                self.service.process_detection(
                    risky_detection,
                    baseline_data=None,
                    now=100.0 + second,
                )
            )

            if (
                current["risk_event"].get(
                    "event_active"
                )
                is True
            ):
                event_result = current
                break

        self.assertIsNotNone(
            event_result,
            msg=(
                "Test setup could not create an active "
                "Risk Event from repeated risky posture."
            ),
        )

        event_before_gap = (
            event_result["risk_event"]["event"]
        )

        self.assertIsNotNone(
            event_before_gap
        )

        level_before_gap = (
            event_result["risk_event"][
                "current_risk_level"
            ]
        )

        # ----------------------------------------------------
        # Lose evaluable posture context.
        # ----------------------------------------------------

        gap_detection = make_detection(
            context_state="UNKNOWN",
            allow_posture_evaluation=False,
            shoulder_tilt=25.0,
            neck_lateral_tilt=25.0,
            neck_flexion=30.0,
        )

        gap_time = (
            event_result[
                "timestamp_monotonic"
            ]
            + 1.0
        )

        gap = self.service.process_detection(
            gap_detection,
            baseline_data=None,
            now=gap_time,
        )

        self.assertNotEqual(
            gap["risk"]["status"],
            "EVALUATED",
        )

        self.assertEqual(
            gap["risk_event"]["event_action"],
            "DATA_GAP",
        )

        self.assertTrue(
            gap["risk_event"]["event_active"],
        )

        self.assertIsNotNone(
            gap["risk_event"]["event"],
        )

        # Missing data must not rewrite the Event's meaningful
        # risk level to NONE/LOW/None.
        self.assertEqual(
            gap["risk_event"][
                "current_risk_level"
            ],
            level_before_gap,
        )

        self.assertTrue(
            gap["risk_event"]["event"][
                "active"
            ]
        )


if __name__ == "__main__":
    unittest.main()
