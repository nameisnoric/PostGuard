from __future__ import annotations

import unittest

from camera_card.posture_assessment.current_posture_assessment import (
    assess_current_posture,
)

from camera_card.temporal_tracking.temporal_posture_tracker import (
    TemporalPostureTracker,
)

from camera_card.risk_evaluation import (
    evaluate_risk,
)


# ============================================================
# REAL ASSESSMENT INPUT CONTRACT BUILDER
# ============================================================

def make_detection(
    *,
    shoulder=0.0,
    lateral=0.0,
    flexion=0.0,
):

    return {
        "contract_version": "1.0",

        "timestamp": 1000.0,

        "context": {
            "state": "VALID",

            "allow_posture_evaluation": True,

            "reason": "TEST_CONTEXT_VALID",

            "stable_seconds": 5.0,
        },

        "features": {
            "shoulder_tilt": {
                "valid": True,
                "value": float(
                    shoulder
                ),
                "unit": "deg",
                "reason": "OK",
            },

            "neck_lateral_tilt": {
                "valid": True,
                "value": float(
                    lateral
                ),
                "unit": "deg",
                "reason": "OK",
            },

            "neck_flexion": {
                "valid": True,
                "value": float(
                    flexion
                ),
                "unit": "deg",
                "reason": "OK",
            },
        },
    }


# ============================================================
# E2E TESTS
# ============================================================

class TestRiskPipelineV12(
    unittest.TestCase
):

    # ========================================================
    # REAL NEUTRAL PIPELINE
    # ========================================================

    def test_real_neutral_pipeline_is_none(
        self,
    ):

        detection = make_detection()

        assessment = (
            assess_current_posture(
                detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        temporal = tracker.update(
            assessment,
            now=100.0,
        )

        risk = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            assessment[
                "contract_version"
            ],
            "1.1",
        )

        self.assertEqual(
            temporal[
                "contract_version"
            ],
            "1.0",
        )

        self.assertEqual(
            risk[
                "risk_contract_version"
            ],
            "1.2",
        )

        self.assertEqual(
            risk[
                "status"
            ],
            "EVALUATED",
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "NONE",
        )

    # ========================================================
    # REAL FLEXION 20 SEC -> LOW
    # ========================================================

    def test_real_flexion_20_seconds_is_low(
        self,
    ):

        detection = make_detection(
            flexion=12.0,
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        temporal = tracker.update(
            assessment,
            now=120.0,
        )

        risk = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "continuous_seconds"
            ],
            20.0,
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "LOW",
        )

    # ========================================================
    # REAL FLEXION EXACTLY 60 SEC -> MODERATE
    # ========================================================

    def test_real_flexion_60_seconds_is_moderate(
        self,
    ):

        detection = make_detection(
            flexion=12.0,
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        temporal = tracker.update(
            assessment,
            now=160.0,
        )

        risk = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "continuous_seconds"
            ],
            60.0,
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "MODERATE",
        )

    # ========================================================
    # REAL TWO GROUPS + STATIC -> HIGH
    # ========================================================

    def test_real_two_groups_with_static_is_high(
        self,
    ):

        detection = make_detection(

            # Current Assessment:
            # > +4 -> RIGHT_SHOULDER_HIGH
            shoulder=5.0,

            # > +10 -> FLEXION
            flexion=12.0,
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        temporal = tracker.update(
            assessment,
            now=160.0,
        )

        risk = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            risk[
                "evidence_groups"
            ][
                "LATERAL_ASYMMETRY"
            ][
                "active"
            ],
            True,
        )

        self.assertEqual(
            risk[
                "evidence_groups"
            ][
                "NECK_SAGITTAL"
            ][
                "active"
            ],
            True,
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "HIGH",
        )

    # ========================================================
    # NEUTRAL BREAKS DURATION
    # ========================================================

    def test_real_neutral_breaks_old_flexion_duration(
        self,
    ):

        active_detection = (
            make_detection(
                flexion=12.0,
            )
        )

        active_assessment = (
            assess_current_posture(
                active_detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            active_assessment,
            now=100.0,
        )

        active_temporal = tracker.update(
            active_assessment,
            now=200.0,
        )

        active_risk = evaluate_risk(
            active_assessment,
            active_temporal,
        )

        self.assertEqual(
            active_risk[
                "risk_level"
            ],
            "MODERATE",
        )

        # ----------------------------------------------------
        # User returns to neutral.
        # ----------------------------------------------------

        neutral_detection = (
            make_detection(
                flexion=0.0,
            )
        )

        neutral_assessment = (
            assess_current_posture(
                neutral_detection
            )
        )

        neutral_temporal = tracker.update(
            neutral_assessment,
            now=201.0,
        )

        neutral_risk = evaluate_risk(
            neutral_assessment,
            neutral_temporal,
        )

        self.assertEqual(
            neutral_temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "continuous_seconds"
            ],
            0.0,
        )

        self.assertIsNone(
            neutral_temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "factor"
            ]
        )

        self.assertEqual(
            neutral_risk[
                "risk_level"
            ],
            "NONE",
        )

    # ========================================================
    # FACTOR DIRECTION CHANGE RESETS DURATION
    # ========================================================

    def test_real_direction_change_restarts_duration(
        self,
    ):

        left_detection = (
            make_detection(
                lateral=8.0,
            )
        )

        left_assessment = (
            assess_current_posture(
                left_detection
            )
        )

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            left_assessment,
            now=100.0,
        )

        left_temporal = tracker.update(
            left_assessment,
            now=200.0,
        )

        left_risk = evaluate_risk(
            left_assessment,
            left_temporal,
        )

        self.assertEqual(
            left_risk[
                "risk_level"
            ],
            "MODERATE",
        )

        # ----------------------------------------------------
        # Switch from TILT_LEFT to TILT_RIGHT.
        #
        # Assessment threshold:
        # right < -7
        # ----------------------------------------------------

        right_detection = (
            make_detection(
                lateral=-8.0,
            )
        )

        right_assessment = (
            assess_current_posture(
                right_detection
            )
        )

        right_temporal = tracker.update(
            right_assessment,
            now=201.0,
        )

        right_risk = evaluate_risk(
            right_assessment,
            right_temporal,
        )

        self.assertEqual(
            right_temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )

        self.assertEqual(
            right_risk[
                "risk_level"
            ],
            "LOW",
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )