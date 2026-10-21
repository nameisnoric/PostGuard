from __future__ import annotations

import unittest
from copy import deepcopy

from camera_card.posture_assessment.current_posture_assessment import (
    ASSESSMENT_COMPLETE,
    ASSESSMENT_NOT_EVALUATED,
    ASSESSMENT_PARTIAL,

    LEFT_SHOULDER_HIGH,
    NECK_EXTENSION,
    NECK_FLEXION,
    NECK_TILT_LEFT,
    NECK_TILT_RIGHT,
    RIGHT_SHOULDER_HIGH,

    assess_current_posture,
)

from camera_card.temporal_tracking.temporal_posture_tracker import (
    TEMPORAL_ACTIVE,
    TEMPORAL_COMPLETE,
    TEMPORAL_NEUTRAL,
    TEMPORAL_NOT_EVALUATED,
    TEMPORAL_OVERALL_NOT_EVALUATED,
    TEMPORAL_PARTIAL,

    TemporalPostureTracker,
)


# ============================================================
# DETECTION BUILDERS
# ============================================================

def valid_feature(
    value,
    unit="deg",
):
    return {
        "valid": True,
        "value": value,
        "unit": unit,
        "reason": "OK",
        "status": "validated_prototype",
    }


def invalid_feature(
    reason="LANDMARK_MISSING",
    unit="deg",
):
    return {
        "valid": False,
        "value": None,
        "unit": unit,
        "reason": reason,
        "status": "validated_prototype",
    }


def detection_result(
    *,
    shoulder=0.0,
    neck=0.0,
    flexion=0.0,
    context_state="VALID",
    allow=True,
    timestamp=0.0,
):
    return {
        "contract_version": "1.0",

        "timestamp": timestamp,

        "context": {
            "state": context_state,

            "allow_posture_evaluation": allow,

            "reason": "TEST",

            "stable_seconds": 2.0,
        },

        "features": {
            "shoulder_tilt": (
                valid_feature(
                    shoulder
                )
            ),

            "neck_lateral_tilt": (
                valid_feature(
                    neck
                )
            ),

            "neck_flexion": (
                valid_feature(
                    flexion
                )
            ),
        },
    }


# ============================================================
# E2E HELPER
# ============================================================

def assess_and_track(
    tracker,
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
        tracker.update(
            assessment,
            now=now,
        )
    )

    return (
        assessment,
        temporal,
    )


# ============================================================
# TEST CLASS
# ============================================================

class TestAssessmentTemporalE2E(
    unittest.TestCase
):

    # ========================================================
    # 1. NEUTRAL FLOW
    # ========================================================

    def test_neutral_detection_to_temporal(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment, temporal = (
            assess_and_track(
                tracker,

                detection_result(
                    shoulder=0.0,
                    neck=0.0,
                    flexion=0.0,
                ),

                now=100.0,
            )
        )

        self.assertEqual(
            assessment[
                "status"
            ],
            ASSESSMENT_COMPLETE,
        )

        self.assertEqual(
            temporal[
                "status"
            ],
            TEMPORAL_COMPLETE,
        )

        self.assertEqual(
            temporal[
                "active_factor_count"
            ],
            0,
        )

        for feature in (
            temporal[
                "features"
            ].values()
        ):

            self.assertEqual(
                feature[
                    "state"
                ],
                TEMPORAL_NEUTRAL,
            )

            self.assertEqual(
                feature[
                    "continuous_seconds"
                ],
                0.0,
            )


    # ========================================================
    # 2. NECK LEFT START
    # ========================================================

    def test_neck_left_factor_starts_at_zero(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment, temporal = (
            assess_and_track(
                tracker,

                detection_result(
                    neck=6.0,
                ),

                now=100.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_TILT_LEFT,
        )

        neck = (
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ]
        )

        self.assertEqual(
            neck[
                "state"
            ],
            TEMPORAL_ACTIVE,
        )

        self.assertEqual(
            neck[
                "factor"
            ],
            NECK_TILT_LEFT,
        )

        self.assertEqual(
            neck[
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # 3. SAME FACTOR CONTINUES
    # ========================================================

    def test_neck_left_accumulates(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                neck=6.0,
            )
        )

        assess_and_track(
            tracker,
            detection,
            now=100.0,
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=112.5,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_TILT_LEFT,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            12.5,
        )


    # ========================================================
    # 4. NECK DIRECTION SWITCH
    # ========================================================

    def test_neck_direction_change_restarts(self):

        tracker = (
            TemporalPostureTracker()
        )

        left = (
            detection_result(
                neck=6.0,
            )
        )

        right = (
            detection_result(
                neck=-8.0,
            )
        )

        assess_and_track(
            tracker,
            left,
            now=100.0,
        )

        assess_and_track(
            tracker,
            left,
            now=110.0,
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                right,
                now=115.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_TILT_RIGHT,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "factor"
            ],
            NECK_TILT_RIGHT,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # 5. FACTOR -> NEUTRAL -> SAME FACTOR
    # ========================================================

    def test_neutral_breaks_continuity(self):

        tracker = (
            TemporalPostureTracker()
        )

        active = (
            detection_result(
                neck=6.0,
            )
        )

        neutral = (
            detection_result(
                neck=0.0,
            )
        )

        assess_and_track(
            tracker,
            active,
            now=100.0,
        )

        assess_and_track(
            tracker,
            active,
            now=110.0,
        )

        _, neutral_temporal = (
            assess_and_track(
                tracker,
                neutral,
                now=111.0,
            )
        )

        self.assertEqual(
            neutral_temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "state"
            ],
            TEMPORAL_NEUTRAL,
        )

        _, restarted = (
            assess_and_track(
                tracker,
                active,
                now=120.0,
            )
        )

        self.assertEqual(
            restarted[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # 6. SHOULDER TRACKING
    # ========================================================

    def test_shoulder_factor_continuity(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=5.0,
            )
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=100.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            RIGHT_SHOULDER_HIGH,
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=107.0,
            )
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            7.0,
        )


    # ========================================================
    # 7. SHOULDER SIDE SWITCH
    # ========================================================

    def test_shoulder_direction_change_restarts(self):

        tracker = (
            TemporalPostureTracker()
        )

        right = (
            detection_result(
                shoulder=5.0,
            )
        )

        left = (
            detection_result(
                shoulder=-3.0,
            )
        )

        assess_and_track(
            tracker,
            right,
            now=100.0,
        )

        assess_and_track(
            tracker,
            right,
            now=120.0,
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                left,
                now=125.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            LEFT_SHOULDER_HIGH,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # 8. FLEXION
    # ========================================================

    def test_flexion_accumulates(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                flexion=12.0,
            )
        )

        assessment, _ = (
            assess_and_track(
                tracker,
                detection,
                now=100.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_FLEXION,
        )

        _, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=125.0,
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
            25.0,
        )


    # ========================================================
    # 9. FLEXION -> EXTENSION
    # ========================================================

    def test_flexion_to_extension_restarts(self):

        tracker = (
            TemporalPostureTracker()
        )

        flexion = (
            detection_result(
                flexion=12.0,
            )
        )

        extension = (
            detection_result(
                flexion=-12.0,
            )
        )

        assess_and_track(
            tracker,
            flexion,
            now=100.0,
        )

        assess_and_track(
            tracker,
            flexion,
            now=120.0,
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                extension,
                now=125.0,
            )
        )

        self.assertEqual(
            assessment[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_EXTENSION,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_flexion"
            ][
                "factor"
            ],
            NECK_EXTENSION,
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


    # ========================================================
    # 10. THREE FACTORS INDEPENDENTLY
    # ========================================================

    def test_three_factors_are_tracked_independently(self):

        tracker = (
            TemporalPostureTracker()
        )

        shoulder_only = (
            detection_result(
                shoulder=5.0,
            )
        )

        both = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
            )
        )

        all_three = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
                flexion=12.0,
            )
        )

        assess_and_track(
            tracker,
            shoulder_only,
            now=100.0,
        )

        assess_and_track(
            tracker,
            both,
            now=110.0,
        )

        _, temporal = (
            assess_and_track(
                tracker,
                all_three,
                now=120.0,
            )
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            20.0,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            10.0,
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
            temporal[
                "active_factor_count"
            ],
            3,
        )


    # ========================================================
    # 11. PARTIAL ASSESSMENT
    # ========================================================

    def test_partial_assessment_flows_to_partial_temporal(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
            )
        )

        assess_and_track(
            tracker,
            detection,
            now=100.0,
        )

        partial = deepcopy(
            detection
        )

        partial[
            "features"
        ][
            "neck_lateral_tilt"
        ] = invalid_feature(
            "LANDMARK_MISSING"
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                partial,
                now=105.0,
            )
        )

        self.assertEqual(
            assessment[
                "status"
            ],
            ASSESSMENT_PARTIAL,
        )

        self.assertEqual(
            temporal[
                "status"
            ],
            TEMPORAL_PARTIAL,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "state"
            ],
            TEMPORAL_NOT_EVALUATED,
        )

        # Shoulder remains independently trackable.
        self.assertEqual(
            temporal[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            5.0,
        )


    # ========================================================
    # 12. INVALID CONTEXT
    # ========================================================

    def test_invalid_context_breaks_all_continuity(self):

        tracker = (
            TemporalPostureTracker()
        )

        active = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
                flexion=12.0,
            )
        )

        assess_and_track(
            tracker,
            active,
            now=100.0,
        )

        assess_and_track(
            tracker,
            active,
            now=110.0,
        )

        invalid_context = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
                flexion=12.0,
                context_state="TRANSITION",
                allow=False,
            )
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                invalid_context,
                now=111.0,
            )
        )

        self.assertEqual(
            assessment[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )

        self.assertEqual(
            temporal[
                "status"
            ],
            TEMPORAL_OVERALL_NOT_EVALUATED,
        )

        self.assertEqual(
            temporal[
                "active_factor_count"
            ],
            0,
        )

        for feature in (
            temporal[
                "features"
            ].values()
        ):

            self.assertEqual(
                feature[
                    "state"
                ],
                TEMPORAL_NOT_EVALUATED,
            )

            self.assertIsNone(
                feature[
                    "continuous_seconds"
                ]
            )

        # Returning to same factors starts from 0.
        _, resumed = (
            assess_and_track(
                tracker,
                active,
                now=120.0,
            )
        )

        for feature in (
            resumed[
                "features"
            ].values()
        ):

            self.assertEqual(
                feature[
                    "continuous_seconds"
                ],
                0.0,
            )


    # ========================================================
    # 13. INTERACTION OVERLAP DOES NOT ALTER TEMPORAL
    # ========================================================

    def test_geometric_interaction_does_not_suppress_tracking(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
            )
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=100.0,
            )
        )

        interaction = (
            assessment[
                "interactions"
            ][
                "interactions"
            ][0]
        )

        self.assertTrue(
            interaction[
                "active"
            ]
        )

        self.assertTrue(
            interaction[
                "classification"
            ][
                "classification_overlap"
            ]
        )

        self.assertEqual(
            temporal[
                "active_factor_count"
            ],
            2,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "shoulder_tilt"
            ][
                "state"
            ],
            TEMPORAL_ACTIVE,
        )

        self.assertEqual(
            temporal[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "state"
            ],
            TEMPORAL_ACTIVE,
        )

        self.assertFalse(
            temporal[
                "policy"
            ][
                "uses_interaction_metadata"
            ]
        )


    # ========================================================
    # 14. EXACT ASSESSMENT BOUNDARIES REMAIN NEUTRAL
    # ========================================================

    def test_exact_boundaries_do_not_start_timers(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=4.0,
                neck=5.0,
                flexion=10.0,
            )
        )

        assessment, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=100.0,
            )
        )

        self.assertEqual(
            assessment[
                "factor_count"
            ],
            0,
        )

        self.assertEqual(
            temporal[
                "active_factor_count"
            ],
            0,
        )

        for feature in (
            temporal[
                "features"
            ].values()
        ):

            self.assertEqual(
                feature[
                    "state"
                ],
                TEMPORAL_NEUTRAL,
            )


    # ========================================================
    # 15. NO RISK / ALERT
    # ========================================================

    def test_temporal_layer_still_has_no_risk_or_alert(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=6.0,
                neck=8.0,
                flexion=15.0,
            )
        )

        _, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=100.0,
            )
        )

        _, temporal = (
            assess_and_track(
                tracker,
                detection,
                now=1000.0,
            )
        )

        self.assertIsNone(
            temporal[
                "risk"
            ]
        )

        self.assertIsNone(
            temporal[
                "alert"
            ]
        )

        self.assertFalse(
            temporal[
                "policy"
            ][
                "uses_duration_threshold"
            ]
        )

        self.assertFalse(
            temporal[
                "policy"
            ][
                "calculates_risk"
            ]
        )

        self.assertFalse(
            temporal[
                "policy"
            ][
                "calculates_alert"
            ]
        )


    # ========================================================
    # 16. ASSESSMENT INPUT NOT MUTATED
    # ========================================================

    def test_e2e_does_not_mutate_detection(self):

        tracker = (
            TemporalPostureTracker()
        )

        detection = (
            detection_result(
                shoulder=5.0,
                neck=6.0,
                flexion=12.0,
            )
        )

        before = deepcopy(
            detection
        )

        assess_and_track(
            tracker,
            detection,
            now=100.0,
        )

        self.assertEqual(
            detection,
            before,
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )