from __future__ import annotations

import unittest

from camera_card.risk_evaluation import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    RISK_LEVEL_NONE,
    evaluate_risk,
)


# ============================================================
# TEST DATA BUILDERS
# ============================================================

FEATURE_NAMES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
)


def assessment_feature(
    factor=None,
):

    return {
        "valid": True,
        "status": "EVALUATED",
        "factor": factor,
    }


def temporal_feature(
    factor=None,
    *,
    seconds=0.0,
):

    if factor is None:

        return {
            "state": "NEUTRAL",
            "factor": None,
            "continuous_seconds": 0.0,
        }

    return {
        "state": "ACTIVE",
        "factor": factor,
        "continuous_seconds": float(
            seconds
        ),
    }


def make_assessment(
    *,
    shoulder=None,
    lateral=None,
    flexion=None,
):

    return {
        "assessment_contract_version": "1.1",

        "features": {
            "shoulder_tilt": (
                assessment_feature(
                    shoulder
                )
            ),

            "neck_lateral_tilt": (
                assessment_feature(
                    lateral
                )
            ),

            "neck_flexion": (
                assessment_feature(
                    flexion
                )
            ),
        },
    }


def make_temporal(
    *,
    shoulder=None,
    shoulder_seconds=0.0,
    lateral=None,
    lateral_seconds=0.0,
    flexion=None,
    flexion_seconds=0.0,
):

    return {
        "temporal_contract_version": "1.0",

        "features": {
            "shoulder_tilt": (
                temporal_feature(
                    shoulder,
                    seconds=(
                        shoulder_seconds
                    ),
                )
            ),

            "neck_lateral_tilt": (
                temporal_feature(
                    lateral,
                    seconds=(
                        lateral_seconds
                    ),
                )
            ),

            "neck_flexion": (
                temporal_feature(
                    flexion,
                    seconds=(
                        flexion_seconds
                    ),
                )
            ),
        },
    }


# ============================================================
# TESTS
# ============================================================

class TestRiskLevelMappingV12(
    unittest.TestCase
):

    # ========================================================
    # CONTRACT
    # ========================================================

    def test_contract_is_v12(
        self,
    ):

        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertEqual(
            result[
                "risk_contract_version"
            ],
            "1.2",
        )

        self.assertTrue(
            result[
                "risk_level_mapping_enabled"
            ]
        )

    # ========================================================
    # NONE
    # ========================================================

    def test_zero_groups_is_none(
        self,
    ):

        result = evaluate_risk(
            make_assessment(),
            make_temporal(),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "EVALUATED",
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_NONE,
        )

    # ========================================================
    # LOW
    # ========================================================

    def test_one_group_without_static_is_low(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                flexion="FLEXION",
            ),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=20.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_LOW,
        )

    # ========================================================
    # MODERATE:
    # ONE GROUP + STATIC
    # ========================================================

    def test_one_group_with_static_is_moderate(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                flexion="FLEXION",
            ),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=60.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_MODERATE,
        )

    # ========================================================
    # MODERATE:
    # TWO GROUPS, NO STATIC
    # ========================================================

    def test_two_groups_without_static_is_moderate(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),

                flexion="FLEXION",
            ),

            make_temporal(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),

                shoulder_seconds=20.0,

                flexion="FLEXION",

                flexion_seconds=20.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_MODERATE,
        )

    # ========================================================
    # HIGH
    # ========================================================

    def test_two_groups_with_static_is_high(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                lateral="TILT_LEFT",
                flexion="FLEXION",
            ),

            make_temporal(
                lateral="TILT_LEFT",
                lateral_seconds=20.0,

                flexion="FLEXION",
                flexion_seconds=60.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_HIGH,
        )

    # ========================================================
    # COUPLED FEATURES
    #
    # Shoulder + neck lateral are ONE group.
    # ========================================================

    def test_shoulder_and_lateral_remain_one_group(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),

                lateral="TILT_LEFT",
            ),

            make_temporal(
                shoulder=(
                    "RIGHT_SHOULDER_HIGH"
                ),

                shoulder_seconds=20.0,

                lateral="TILT_LEFT",

                lateral_seconds=20.0,
            ),
        )

        group = (
            result[
                "evidence_groups"
            ][
                "LATERAL_ASYMMETRY"
            ]
        )

        self.assertEqual(
            len(
                group[
                    "active_features"
                ]
            ),
            2,
        )

        self.assertEqual(
            result[
                "risk_level_mapping"
            ][
                "active_group_count"
            ],
            1,
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_LOW,
        )

    # ========================================================
    # 59.999 BOUNDARY
    # ========================================================

    def test_59_999_is_not_static(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                flexion="FLEXION",
            ),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=59.999,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_LOW,
        )

    # ========================================================
    # EXACT 60 BOUNDARY
    # ========================================================

    def test_exact_60_is_static(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                flexion="FLEXION",
            ),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=60.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_MODERATE,
        )

    # ========================================================
    # 60.001 BOUNDARY
    # ========================================================

    def test_60_001_is_static(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                flexion="FLEXION",
            ),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=60.001,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_MODERATE,
        )

    # ========================================================
    # FACTOR MISMATCH
    # ========================================================

    def test_factor_mismatch_has_no_risk_level(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                lateral="TILT_LEFT",
            ),

            make_temporal(
                lateral="TILT_RIGHT",
                lateral_seconds=120.0,
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "PARTIAL",
        )

        self.assertFalse(
            result[
                "risk_level_available"
            ]
        )

        self.assertIsNone(
            result[
                "risk_level"
            ]
        )

    # ========================================================
    # NEUTRAL VS OLD ACTIVE TEMPORAL
    # ========================================================

    def test_neutral_vs_stale_active_temporal_is_partial(
        self,
    ):

        result = evaluate_risk(

            make_assessment(),

            make_temporal(
                flexion="FLEXION",
                flexion_seconds=120.0,
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "PARTIAL",
        )

        self.assertIsNone(
            result[
                "risk_level"
            ]
        )

    # ========================================================
    # INCOMPLETE ASSESSMENT
    # ========================================================

    def test_missing_required_assessment_is_not_none(
        self,
    ):

        assessment = (
            make_assessment()
        )

        assessment[
            "features"
        ][
            "neck_flexion"
        ] = {
            "valid": False,
            "status": "NOT_EVALUATED",
            "factor": None,
        }

        temporal = (
            make_temporal()
        )

        temporal[
            "features"
        ][
            "neck_flexion"
        ] = {
            "state": "NOT_EVALUATED",
            "factor": None,
            "continuous_seconds": None,
        }

        result = evaluate_risk(
            assessment,
            temporal,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "PARTIAL",
        )

        self.assertIsNone(
            result[
                "risk_level"
            ]
        )

    # ========================================================
    # FUTURE LAYERS STILL DISABLED
    # ========================================================

    def test_risk_event_and_alert_still_disabled(
        self,
    ):

        result = evaluate_risk(

            make_assessment(
                lateral="TILT_LEFT",
                flexion="FLEXION",
            ),

            make_temporal(
                lateral="TILT_LEFT",
                lateral_seconds=120.0,

                flexion="FLEXION",
                flexion_seconds=120.0,
            ),
        )

        self.assertEqual(
            result[
                "risk_level"
            ],
            RISK_LEVEL_HIGH,
        )

        self.assertIsNone(
            result[
                "risk_score"
            ]
        )

        self.assertIsNone(
            result[
                "risk_event"
            ]
        )

        self.assertIsNone(
            result[
                "alert"
            ]
        )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )