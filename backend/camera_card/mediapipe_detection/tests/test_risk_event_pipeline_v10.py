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

from camera_card.risk_event import (
    RiskEventTracker,
)


# ============================================================
# DETECTION CONTRACT BUILDER
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
# HELPER
# ============================================================

def assess_track_risk(
    temporal_tracker,
    detection,
    *,
    now,
):

    assessment = (
        assess_current_posture(
            detection
        )
    )

    temporal = (
        temporal_tracker.update(
            assessment,
            now=now,
        )
    )

    risk = (
        evaluate_risk(
            assessment,
            temporal,
        )
    )

    return (
        assessment,
        temporal,
        risk,
    )


# ============================================================
# E2E TESTS
# ============================================================

class TestRiskEventPipelineV10(
    unittest.TestCase
):

    # ========================================================
    # NONE -> NO EVENT
    # ========================================================

    def test_real_none_does_not_start_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        (
            _,
            _,
            risk,
        ) = assess_track_risk(
            temporal_tracker,
            make_detection(),
            now=100.0,
        )

        event = (
            event_tracker.update(
                risk,
                now=100.0,
            )
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "NONE",
        )

        self.assertEqual(
            event[
                "event_action"
            ],
            "NONE",
        )

        self.assertFalse(
            event[
                "event_active"
            ]
        )

    # ========================================================
    # FLEXION 20 SEC -> LOW -> NO EVENT
    # ========================================================

    def test_real_low_does_not_start_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        assess_track_risk(
            temporal_tracker,
            detection,
            now=100.0,
        )

        (
            _,
            _,
            risk,
        ) = assess_track_risk(
            temporal_tracker,
            detection,
            now=120.0,
        )

        event = (
            event_tracker.update(
                risk,
                now=120.0,
            )
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "LOW",
        )

        self.assertEqual(
            event[
                "event_action"
            ],
            "NONE",
        )

    # ========================================================
    # FLEXION 60 SEC -> MODERATE -> START
    # ========================================================

    def test_real_moderate_starts_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        assess_track_risk(
            temporal_tracker,
            detection,
            now=100.0,
        )

        (
            _,
            _,
            risk,
        ) = assess_track_risk(
            temporal_tracker,
            detection,
            now=160.0,
        )

        event = (
            event_tracker.update(
                risk,
                now=160.0,
            )
        )

        self.assertEqual(
            risk[
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            event[
                "event_action"
            ],
            "STARTED",
        )

        self.assertTrue(
            event[
                "event_active"
            ]
        )

    # ========================================================
    # MODERATE -> HIGH
    # ========================================================

    def test_real_moderate_to_high_escalates_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        # ----------------------------------------------------
        # First create MODERATE:
        # flexion >= 60 seconds
        # ----------------------------------------------------

        flexion_only = (
            make_detection(
                flexion=12.0,
            )
        )

        assess_track_risk(
            temporal_tracker,
            flexion_only,
            now=100.0,
        )

        (
            _,
            _,
            moderate_risk,
        ) = assess_track_risk(
            temporal_tracker,
            flexion_only,
            now=160.0,
        )

        first_event = (
            event_tracker.update(
                moderate_risk,
                now=160.0,
            )
        )

        self.assertEqual(
            moderate_risk[
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            first_event[
                "event_action"
            ],
            "STARTED",
        )

        # ----------------------------------------------------
        # Add shoulder factor.
        #
        # neck flexion still has static-duration evidence.
        #
        # Active groups:
        #
        # LATERAL_ASYMMETRY
        # NECK_SAGITTAL
        #
        # => HIGH
        # ----------------------------------------------------

        shoulder_and_flexion = (
            make_detection(
                shoulder=5.0,
                flexion=12.0,
            )
        )

        (
            _,
            _,
            high_risk,
        ) = assess_track_risk(
            temporal_tracker,
            shoulder_and_flexion,
            now=161.0,
        )

        second_event = (
            event_tracker.update(
                high_risk,
                now=161.0,
            )
        )

        self.assertEqual(
            high_risk[
                "risk_level"
            ],
            "HIGH",
        )

        self.assertEqual(
            second_event[
                "event_action"
            ],
            "ESCALATED",
        )

        self.assertEqual(
            first_event[
                "event"
            ][
                "runtime_event_id"
            ],
            second_event[
                "event"
            ][
                "runtime_event_id"
            ],
        )

    # ========================================================
    # HIGH -> MODERATE
    #
    # EVENT REMAINS ACTIVE
    # ========================================================

    def test_real_high_to_moderate_deescalates_same_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        # ----------------------------------------------------
        # Start both groups.
        # ----------------------------------------------------

        high_detection = (
            make_detection(
                shoulder=5.0,
                flexion=12.0,
            )
        )

        assess_track_risk(
            temporal_tracker,
            high_detection,
            now=100.0,
        )

        (
            _,
            _,
            high_risk,
        ) = assess_track_risk(
            temporal_tracker,
            high_detection,
            now=160.0,
        )

        high_event = (
            event_tracker.update(
                high_risk,
                now=160.0,
            )
        )

        self.assertEqual(
            high_risk[
                "risk_level"
            ],
            "HIGH",
        )

        event_id = (
            high_event[
                "event"
            ][
                "runtime_event_id"
            ]
        )

        # ----------------------------------------------------
        # Shoulder returns neutral.
        #
        # Flexion remains >= 60 seconds.
        #
        # One active group + static duration
        # => MODERATE
        # ----------------------------------------------------

        moderate_detection = (
            make_detection(
                shoulder=0.0,
                flexion=12.0,
            )
        )

        (
            _,
            _,
            moderate_risk,
        ) = assess_track_risk(
            temporal_tracker,
            moderate_detection,
            now=161.0,
        )

        moderate_event = (
            event_tracker.update(
                moderate_risk,
                now=161.0,
            )
        )

        self.assertEqual(
            moderate_risk[
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            moderate_event[
                "event_action"
            ],
            "DEESCALATED",
        )

        self.assertTrue(
            moderate_event[
                "event_active"
            ]
        )

        self.assertEqual(
            moderate_event[
                "event"
            ][
                "runtime_event_id"
            ],
            event_id,
        )

        self.assertEqual(
            moderate_event[
                "event"
            ][
                "peak_risk_level"
            ],
            "HIGH",
        )

    # ========================================================
    # MODERATE -> NONE -> RESOLVED
    # ========================================================

    def test_real_return_to_neutral_resolves_event(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        risky_detection = (
            make_detection(
                flexion=12.0,
            )
        )

        assess_track_risk(
            temporal_tracker,
            risky_detection,
            now=100.0,
        )

        (
            _,
            _,
            moderate_risk,
        ) = assess_track_risk(
            temporal_tracker,
            risky_detection,
            now=160.0,
        )

        started = (
            event_tracker.update(
                moderate_risk,
                now=160.0,
            )
        )

        event_id = (
            started[
                "event"
            ][
                "runtime_event_id"
            ]
        )

        # ----------------------------------------------------
        # User returns to neutral.
        # Temporal resets duration automatically.
        # ----------------------------------------------------

        neutral_detection = (
            make_detection()
        )

        (
            _,
            temporal,
            neutral_risk,
        ) = assess_track_risk(
            temporal_tracker,
            neutral_detection,
            now=161.0,
        )

        resolved = (
            event_tracker.update(
                neutral_risk,
                now=161.0,
            )
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "continuous_seconds"
            ],
            0.0,
        )

        self.assertEqual(
            neutral_risk[
                "risk_level"
            ],
            "NONE",
        )

        self.assertEqual(
            resolved[
                "event_action"
            ],
            "RESOLVED",
        )

        self.assertFalse(
            resolved[
                "event_active"
            ]
        )

        self.assertEqual(
            resolved[
                "resolved_event"
            ][
                "runtime_event_id"
            ],
            event_id,
        )

    # ========================================================
    # CONTRACT CHAIN
    # ========================================================

    def test_complete_contract_chain(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        assessment = (
            assess_current_posture(
                detection
            )
        )

        temporal = (
            temporal_tracker.update(
                assessment,
                now=100.0,
            )
        )

        risk = (
            evaluate_risk(
                assessment,
                temporal,
            )
        )

        event = (
            event_tracker.update(
                risk,
                now=100.0,
            )
        )

        self.assertEqual(
            detection[
                "contract_version"
            ],
            "1.0",
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
            event[
                "risk_event_contract_version"
            ],
            "1.0",
        )

        # Alert still belongs to future layer.
        self.assertIsNone(
            event[
                "alert"
            ]
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )