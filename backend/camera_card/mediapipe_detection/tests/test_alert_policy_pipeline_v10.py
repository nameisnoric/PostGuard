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

from camera_card.alert_policy import (
    AlertPolicy,
    AlertPolicyConfig,
)


# ============================================================
# TEST CONFIG
#
# IMPORTANT:
#
# 600 / 300 seconds are prototype experimental values.
#
# They are NOT medical standards.
# ============================================================

def make_alert_policy():

    return AlertPolicy(
        AlertPolicyConfig(
            # Event is already confirmed by upstream layers,
            # so test prototype allows immediate first alert.
            moderate_first_alert_delay_seconds=0.0,
            high_first_alert_delay_seconds=0.0,

            # Experimental prototype repeat timing.
            moderate_repeat_cooldown_seconds=600.0,
            high_repeat_cooldown_seconds=300.0,

            escalation_bypasses_cooldown=True,

            notify_on_resolution=False,
        )
    )


# ============================================================
# DETECTION BUILDER
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
# PIPELINE HELPER
# ============================================================

def process_pipeline(
    *,
    temporal_tracker,
    event_tracker,
    alert_policy,
    detection,
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

    event = (
        event_tracker.update(
            risk,
            now=now,
        )
    )

    alert = (
        alert_policy.update(
            event,
            now=now,
        )
    )

    return {
        "assessment": assessment,
        "temporal": temporal,
        "risk": risk,
        "event": event,
        "alert": alert,
    }


# ============================================================
# E2E TESTS
# ============================================================

class TestAlertPolicyPipelineV10(
    unittest.TestCase
):

    # ========================================================
    # COMPLETE CONTRACT CHAIN
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

        alert_policy = (
            make_alert_policy()
        )

        result = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,

            detection=make_detection(),

            now=100.0,
        )

        self.assertEqual(
            result[
                "assessment"
            ][
                "contract_version"
            ],
            "1.1",
        )

        self.assertEqual(
            result[
                "temporal"
            ][
                "contract_version"
            ],
            "1.0",
        )

        self.assertEqual(
            result[
                "risk"
            ][
                "risk_contract_version"
            ],
            "1.2",
        )

        self.assertEqual(
            result[
                "event"
            ][
                "risk_event_contract_version"
            ],
            "1.0",
        )

        self.assertEqual(
            result[
                "alert"
            ][
                "alert_policy_contract_version"
            ],
            "1.0",
        )

        self.assertIsNone(
            result[
                "alert"
            ][
                "notification"
            ]
        )

    # ========================================================
    # NONE -> NO ALERT
    # ========================================================

    def test_real_none_produces_no_alert(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        result = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,

            detection=make_detection(),

            now=100.0,
        )

        self.assertEqual(
            result[
                "risk"
            ][
                "risk_level"
            ],
            "NONE",
        )

        self.assertEqual(
            result[
                "event"
            ][
                "event_action"
            ],
            "NONE",
        )

        self.assertFalse(
            result[
                "alert"
            ][
                "should_notify"
            ]
        )

    # ========================================================
    # LOW -> NO ALERT
    # ========================================================

    def test_real_low_produces_no_alert(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=100.0,
        )

        result = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=120.0,
        )

        self.assertEqual(
            result[
                "risk"
            ][
                "risk_level"
            ],
            "LOW",
        )

        self.assertEqual(
            result[
                "event"
            ][
                "event_action"
            ],
            "NONE",
        )

        self.assertFalse(
            result[
                "alert"
            ][
                "should_notify"
            ]
        )

    # ========================================================
    # MODERATE -> FIRST ALERT
    # ========================================================

    def test_real_moderate_starts_first_alert(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=100.0,
        )

        result = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=160.0,
        )

        self.assertEqual(
            result[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertEqual(
            result[
                "event"
            ][
                "event_action"
            ],
            "STARTED",
        )

        self.assertTrue(
            result[
                "alert"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            result[
                "alert"
            ][
                "alert_type"
            ],
            "FIRST",
        )

    # ========================================================
    # NO FRAME-SPAM
    # ========================================================

    def test_real_moderate_does_not_alert_next_frame(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=100.0,
        )

        first = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=160.0,
        )

        self.assertTrue(
            first[
                "alert"
            ][
                "should_notify"
            ]
        )

        next_frame = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=161.0,
        )

        self.assertEqual(
            next_frame[
                "event"
            ][
                "event_action"
            ],
            "UPDATED",
        )

        self.assertFalse(
            next_frame[
                "alert"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            next_frame[
                "alert"
            ][
                "decision"
            ],
            "SUPPRESSED",
        )

    # ========================================================
    # MODERATE REPEAT AFTER 10 MINUTES
    # ========================================================

    def test_real_moderate_repeat_after_600_seconds(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        detection = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=100.0,
        )

        first = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=160.0,
        )

        self.assertTrue(
            first[
                "alert"
            ][
                "should_notify"
            ]
        )

        repeat = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=detection,
            now=760.0,
        )

        self.assertEqual(
            repeat[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertTrue(
            repeat[
                "alert"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            repeat[
                "alert"
            ][
                "alert_type"
            ],
            "REPEAT",
        )

    # ========================================================
    # MODERATE -> HIGH -> ESCALATION ALERT
    # ========================================================

    def test_real_escalation_alerts_immediately(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        flexion_only = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=flexion_only,
            now=100.0,
        )

        moderate = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=flexion_only,
            now=160.0,
        )

        self.assertEqual(
            moderate[
                "risk"
            ][
                "risk_level"
            ],
            "MODERATE",
        )

        self.assertTrue(
            moderate[
                "alert"
            ][
                "should_notify"
            ]
        )

        high_detection = (
            make_detection(
                shoulder=5.0,
                flexion=12.0,
            )
        )

        high = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=high_detection,
            now=161.0,
        )

        self.assertEqual(
            high[
                "risk"
            ][
                "risk_level"
            ],
            "HIGH",
        )

        self.assertEqual(
            high[
                "event"
            ][
                "event_action"
            ],
            "ESCALATED",
        )

        self.assertTrue(
            high[
                "alert"
            ][
                "should_notify"
            ]
        )

        self.assertEqual(
            high[
                "alert"
            ][
                "alert_type"
            ],
            "ESCALATION",
        )

    # ========================================================
    # HIGH -> MODERATE DOES NOT ALERT
    # ========================================================

    def test_real_deescalation_does_not_alert(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        high_detection = (
            make_detection(
                shoulder=5.0,
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=high_detection,
            now=100.0,
        )

        high = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=high_detection,
            now=160.0,
        )

        self.assertEqual(
            high[
                "risk"
            ][
                "risk_level"
            ],
            "HIGH",
        )

        moderate_detection = (
            make_detection(
                shoulder=0.0,
                flexion=12.0,
            )
        )

        result = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=moderate_detection,
            now=161.0,
        )

        self.assertEqual(
            result[
                "event"
            ][
                "event_action"
            ],
            "DEESCALATED",
        )

        self.assertFalse(
            result[
                "alert"
            ][
                "should_notify"
            ]
        )

    # ========================================================
    # RETURN TO NEUTRAL -> RESOLVE
    # ========================================================

    def test_real_resolution_clears_alert_state(
        self,
    ):

        temporal_tracker = (
            TemporalPostureTracker()
        )

        event_tracker = (
            RiskEventTracker()
        )

        alert_policy = (
            make_alert_policy()
        )

        risky = (
            make_detection(
                flexion=12.0,
            )
        )

        process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=risky,
            now=100.0,
        )

        moderate = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=risky,
            now=160.0,
        )

        self.assertTrue(
            moderate[
                "alert"
            ][
                "should_notify"
            ]
        )

        neutral = process_pipeline(
            temporal_tracker=temporal_tracker,
            event_tracker=event_tracker,
            alert_policy=alert_policy,
            detection=make_detection(),
            now=161.0,
        )

        self.assertEqual(
            neutral[
                "risk"
            ][
                "risk_level"
            ],
            "NONE",
        )

        self.assertEqual(
            neutral[
                "event"
            ][
                "event_action"
            ],
            "RESOLVED",
        )

        self.assertFalse(
            neutral[
                "alert"
            ][
                "should_notify"
            ]
        )

        self.assertIsNone(
            alert_policy.get_active_state()
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )