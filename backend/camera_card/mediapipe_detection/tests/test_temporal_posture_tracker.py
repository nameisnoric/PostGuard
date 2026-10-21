from __future__ import annotations

import unittest
from copy import deepcopy

from camera_card.temporal_tracking.temporal_posture_tracker import (
    TEMPORAL_ACTIVE,
    TEMPORAL_COMPLETE,
    TEMPORAL_CONTRACT_VERSION,
    TEMPORAL_NEUTRAL,
    TEMPORAL_NOT_EVALUATED,
    TEMPORAL_OVERALL_NOT_EVALUATED,
    TEMPORAL_PARTIAL,
    TemporalPostureTracker,
)


# ============================================================
# ASSESSMENT BUILDERS
# ============================================================

def assessment_feature(
    *,
    status,
    is_factor,
    evaluated=True,
    reason="RULE_MATCH",
):
    return {
        "feature": "test",
        "status": status,
        "reason": reason,
        "current": 0.0,
        "unit": "deg",
        "evaluated": evaluated,
        "is_posture_factor": is_factor,
    }


def neutral_assessment():
    return {
        "contract_version": "1.1",
        "timestamp": 123.0,
        "status": "COMPLETE",
        "evaluable": True,

        "features": {
            "shoulder_tilt": (
                assessment_feature(
                    status="NEAR_LEVEL",
                    is_factor=False,
                )
            ),

            "neck_lateral_tilt": (
                assessment_feature(
                    status="NEUTRAL",
                    is_factor=False,
                )
            ),

            "neck_flexion": (
                assessment_feature(
                    status="NEUTRAL",
                    is_factor=False,
                )
            ),
        },

        "risk": None,
        "alert": None,
    }


def factor_assessment(
    *,
    shoulder="NEAR_LEVEL",
    shoulder_factor=False,

    neck="NEUTRAL",
    neck_factor=False,

    flexion="NEUTRAL",
    flexion_factor=False,
):
    result = neutral_assessment()

    result[
        "features"
    ][
        "shoulder_tilt"
    ] = assessment_feature(
        status=shoulder,
        is_factor=shoulder_factor,
    )

    result[
        "features"
    ][
        "neck_lateral_tilt"
    ] = assessment_feature(
        status=neck,
        is_factor=neck_factor,
    )

    result[
        "features"
    ][
        "neck_flexion"
    ] = assessment_feature(
        status=flexion,
        is_factor=flexion_factor,
    )

    return result


# ============================================================
# TEST CLASS
# ============================================================

class TestTemporalPostureTracker(
    unittest.TestCase
):

    # ========================================================
    # CONTRACT
    # ========================================================

    def test_contract_version(self):

        tracker = (
            TemporalPostureTracker()
        )

        result = tracker.update(
            neutral_assessment(),
            now=100.0,
        )

        self.assertEqual(
            result[
                "contract_version"
            ],
            TEMPORAL_CONTRACT_VERSION,
        )

        self.assertEqual(
            result[
                "source_assessment_contract_version"
            ],
            "1.1",
        )


    # ========================================================
    # NEUTRAL
    # ========================================================

    def test_all_neutral(self):

        tracker = (
            TemporalPostureTracker()
        )

        result = tracker.update(
            neutral_assessment(),
            now=100.0,
        )

        self.assertEqual(
            result[
                "status"
            ],
            TEMPORAL_COMPLETE,
        )

        self.assertEqual(
            result[
                "active_factor_count"
            ],
            0,
        )

        for feature in (
            result[
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
    # START FACTOR
    # ========================================================

    def test_factor_starts_at_zero(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        result = tracker.update(
            assessment,
            now=100.0,
        )

        neck = (
            result[
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
            "TILT_LEFT",
        )

        self.assertEqual(
            neck[
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # CONTINUOUS SAME FACTOR
    # ========================================================

    def test_same_factor_accumulates_time(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        result = tracker.update(
            assessment,
            now=112.5,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            12.5,
        )


    # ========================================================
    # DIRECTION / FACTOR SWITCH
    # ========================================================

    def test_factor_change_resets_duration(self):

        tracker = (
            TemporalPostureTracker()
        )

        left = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        right = (
            factor_assessment(
                neck="TILT_RIGHT",
                neck_factor=True,
            )
        )

        tracker.update(
            left,
            now=100.0,
        )

        tracker.update(
            left,
            now=120.0,
        )

        result = tracker.update(
            right,
            now=125.0,
        )

        neck = (
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ]
        )

        self.assertEqual(
            neck[
                "factor"
            ],
            "TILT_RIGHT",
        )

        self.assertEqual(
            neck[
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # NEUTRAL RESET
    # ========================================================

    def test_neutral_resets_duration(self):

        tracker = (
            TemporalPostureTracker()
        )

        factor = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,
            )
        )

        tracker.update(
            factor,
            now=100.0,
        )

        tracker.update(
            factor,
            now=110.0,
        )

        neutral_result = tracker.update(
            neutral_assessment(),
            now=111.0,
        )

        shoulder = (
            neutral_result[
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            shoulder[
                "state"
            ],
            TEMPORAL_NEUTRAL,
        )

        self.assertEqual(
            shoulder[
                "continuous_seconds"
            ],
            0.0,
        )

        restarted = tracker.update(
            factor,
            now=120.0,
        )

        self.assertEqual(
            restarted[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # NOT EVALUATED RESET
    # ========================================================

    def test_not_evaluated_resets_duration(self):

        tracker = (
            TemporalPostureTracker()
        )

        active = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        tracker.update(
            active,
            now=100.0,
        )

        tracker.update(
            active,
            now=110.0,
        )

        invalid = deepcopy(
            active
        )

        invalid[
            "features"
        ][
            "neck_lateral_tilt"
        ] = assessment_feature(
            status="NOT_EVALUATED",
            is_factor=False,
            evaluated=False,
            reason="CONTEXT_NOT_VALID:TRANSITION",
        )

        result = tracker.update(
            invalid,
            now=111.0,
        )

        neck = (
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ]
        )

        self.assertEqual(
            neck[
                "state"
            ],
            TEMPORAL_NOT_EVALUATED,
        )

        self.assertIsNone(
            neck[
                "continuous_seconds"
            ]
        )

        resumed = tracker.update(
            active,
            now=120.0,
        )

        self.assertEqual(
            resumed[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # PARTIAL FEATURE
    # ========================================================

    def test_partial_assessment_tracks_other_features(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,

                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        partial = deepcopy(
            assessment
        )

        partial[
            "features"
        ][
            "neck_lateral_tilt"
        ] = assessment_feature(
            status="NOT_EVALUATED",
            is_factor=False,
            evaluated=False,
            reason="LANDMARK_MISSING",
        )

        result = tracker.update(
            partial,
            now=105.0,
        )

        self.assertEqual(
            result[
                "status"
            ],
            TEMPORAL_PARTIAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            5.0,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "state"
            ],
            TEMPORAL_NOT_EVALUATED,
        )


    # ========================================================
    # INDEPENDENT FEATURE TIMING
    # ========================================================

    def test_features_track_independently(self):

        tracker = (
            TemporalPostureTracker()
        )

        shoulder_only = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,
            )
        )

        tracker.update(
            shoulder_only,
            now=100.0,
        )

        both = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,

                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        result = tracker.update(
            both,
            now=110.0,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "continuous_seconds"
            ],
            10.0,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # MULTIPLE FACTORS
    # ========================================================

    def test_multiple_active_factors(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,

                neck="TILT_LEFT",
                neck_factor=True,

                flexion="FLEXION",
                flexion_factor=True,
            )
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        result = tracker.update(
            assessment,
            now=130.0,
        )

        self.assertEqual(
            result[
                "active_factor_count"
            ],
            3,
        )

        self.assertEqual(
            len(
                result[
                    "active_factors"
                ]
            ),
            3,
        )

        for item in (
            result[
                "active_factors"
            ]
        ):

            self.assertEqual(
                item[
                    "continuous_seconds"
                ],
                30.0,
            )


    # ========================================================
    # ALL NOT EVALUATED
    # ========================================================

    def test_all_not_evaluated(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            neutral_assessment()
        )

        for name in (
            assessment[
                "features"
            ]
        ):

            assessment[
                "features"
            ][
                name
            ] = assessment_feature(
                status="NOT_EVALUATED",
                is_factor=False,
                evaluated=False,
                reason="CONTEXT_NOT_VALID:TRANSITION",
            )

        result = tracker.update(
            assessment,
            now=100.0,
        )

        self.assertEqual(
            result[
                "status"
            ],
            TEMPORAL_OVERALL_NOT_EVALUATED,
        )

        self.assertFalse(
            result[
                "evaluable"
            ]
        )

        self.assertEqual(
            result[
                "active_factor_count"
            ],
            0,
        )


    # ========================================================
    # MISSING FEATURE
    # ========================================================

    def test_missing_feature_not_evaluated(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            neutral_assessment()
        )

        del assessment[
            "features"
        ][
            "shoulder_tilt"
        ]

        result = tracker.update(
            assessment,
            now=100.0,
        )

        self.assertEqual(
            result[
                "status"
            ],
            TEMPORAL_PARTIAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "state"
            ],
            TEMPORAL_NOT_EVALUATED,
        )


    # ========================================================
    # NO DURATION THRESHOLD
    # ========================================================

    def test_no_sustained_threshold_is_applied(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                flexion="FLEXION",
                flexion_factor=True,
            )
        )

        tracker.update(
            assessment,
            now=0.0,
        )

        result = tracker.update(
            assessment,
            now=10000.0,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "continuous_seconds"
            ],
            10000.0,
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "uses_duration_threshold"
            ]
        )

        self.assertIsNone(
            result[
                "risk"
            ]
        )

        self.assertIsNone(
            result[
                "alert"
            ]
        )


    # ========================================================
    # INTERACTION METADATA DOES NOT CHANGE TRACKING
    # ========================================================

    def test_interaction_metadata_is_not_used(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),
                shoulder_factor=True,

                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        assessment[
            "interactions"
        ] = {
            "contract_version": "1.0",

            "interactions": [{
                "type": (
                    "GEOMETRICALLY_COUPLED"
                ),

                "active": True,
            }],
        }

        result = tracker.update(
            assessment,
            now=100.0,
        )

        self.assertEqual(
            result[
                "active_factor_count"
            ],
            2,
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "uses_interaction_metadata"
            ]
        )


    # ========================================================
    # MONOTONIC CLOCK
    # ========================================================

    def test_clock_cannot_move_backwards(self):

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            neutral_assessment(),
            now=100.0,
        )

        with self.assertRaises(
            ValueError
        ):

            tracker.update(
                neutral_assessment(),
                now=99.0,
            )


    def test_boolean_clock_rejected(self):

        tracker = (
            TemporalPostureTracker()
        )

        with self.assertRaises(
            ValueError
        ):

            tracker.update(
                neutral_assessment(),
                now=True,
            )


    # ========================================================
    # RESET
    # ========================================================

    def test_reset_clears_duration(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        tracker.update(
            assessment,
            now=130.0,
        )

        tracker.reset()

        result = tracker.update(
            assessment,
            now=200.0,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "continuous_seconds"
            ],
            0.0,
        )


    # ========================================================
    # INPUT IMMUTABILITY
    # ========================================================

    def test_assessment_not_mutated(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            )
        )

        before = deepcopy(
            assessment
        )

        tracker.update(
            assessment,
            now=100.0,
        )

        self.assertEqual(
            assessment,
            before,
        )


    # ========================================================
    # INTERNAL STATE COPY
    # ========================================================

    def test_internal_state_copy_is_safe(self):

        tracker = (
            TemporalPostureTracker()
        )

        tracker.update(
            factor_assessment(
                neck="TILT_LEFT",
                neck_factor=True,
            ),
            now=100.0,
        )

        snapshot = (
            tracker.get_internal_state()
        )

        snapshot[
            "neck_lateral_tilt"
        ][
            "factor"
        ] = "BROKEN"

        second = (
            tracker.get_internal_state()
        )

        self.assertEqual(
            second[
                "neck_lateral_tilt"
            ][
                "factor"
            ],
            "TILT_LEFT",
        )


    # ========================================================
    # CONTRACT VALIDATION
    # ========================================================

    def test_bad_assessment_contract_rejected(self):

        tracker = (
            TemporalPostureTracker()
        )

        assessment = (
            neutral_assessment()
        )

        assessment[
            "contract_version"
        ] = "99.0"

        with self.assertRaises(
            ValueError
        ):

            tracker.update(
                assessment,
                now=100.0,
            )


    def test_non_mapping_rejected(self):

        tracker = (
            TemporalPostureTracker()
        )

        with self.assertRaises(
            ValueError
        ):

            tracker.update(
                None,
                now=100.0,
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )