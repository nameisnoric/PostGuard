from __future__ import annotations

import unittest

from camera_card.posture_score import (
    ModifiedRULAError,
    calculate_modified_rula_score,
    modified_rula_to_postguard_score,
)


# ============================================================
# TEST BUILDERS
# ============================================================

def assessment_feature(
    *,
    status: str,
    current: float,
    is_factor: bool,
):
    return {
        "feature": "test",
        "status": status,
        "reason": "RULE_MATCH",
        "current": current,
        "absolute_current": abs(current),
        "thresholds": {},
        "unit": "deg",
        "evaluated": True,
        "is_posture_factor": is_factor,
    }


def temporal_feature(
    *,
    factor,
    seconds: float,
):
    return {
        "feature": "test",
        "state": (
            "ACTIVE"
            if factor is not None
            else
            "NEUTRAL"
        ),
        "reason": "TEST",
        "factor": factor,
        "continuous_seconds": seconds,
        "started_at": 0.0,
        "last_update_at": seconds,
        "evaluable": True,
        "active": (
            factor is not None
        ),
    }


def build_assessment(
    *,
    shoulder_status="NEAR_LEVEL",
    shoulder_angle=0.0,
    neck_lateral_status="NEUTRAL",
    neck_lateral_angle=0.0,
    neck_flexion_status="NEUTRAL",
    neck_flexion_angle=0.0,
):
    return {
        "contract_version": "1.1",

        "status": "COMPLETE",

        "evaluable": True,

        "features": {
            "shoulder_tilt": (
                assessment_feature(
                    status=shoulder_status,
                    current=shoulder_angle,
                    is_factor=(
                        shoulder_status
                        !=
                        "NEAR_LEVEL"
                    ),
                )
            ),

            "neck_lateral_tilt": (
                assessment_feature(
                    status=neck_lateral_status,
                    current=neck_lateral_angle,
                    is_factor=(
                        neck_lateral_status
                        !=
                        "NEUTRAL"
                    ),
                )
            ),

            "neck_flexion": (
                assessment_feature(
                    status=neck_flexion_status,
                    current=neck_flexion_angle,
                    is_factor=(
                        neck_flexion_status
                        !=
                        "NEUTRAL"
                    ),
                )
            ),
        },
    }


def build_temporal(
    *,
    shoulder_factor=None,
    shoulder_seconds=0.0,
    neck_lateral_factor=None,
    neck_lateral_seconds=0.0,
    neck_flexion_factor=None,
    neck_flexion_seconds=0.0,
):
    return {
        "contract_version": "1.0",

        "status": "COMPLETE",

        "features": {
            "shoulder_tilt": (
                temporal_feature(
                    factor=shoulder_factor,
                    seconds=shoulder_seconds,
                )
            ),

            "neck_lateral_tilt": (
                temporal_feature(
                    factor=neck_lateral_factor,
                    seconds=neck_lateral_seconds,
                )
            ),

            "neck_flexion": (
                temporal_feature(
                    factor=neck_flexion_factor,
                    seconds=neck_flexion_seconds,
                )
            ),
        },
    }


# ============================================================
# TESTS
# ============================================================

class ModifiedRULATests(
    unittest.TestCase
):

    def test_score_conversion_1_to_7(
        self,
    ):
        expected = {
            1: 0,
            2: 17,
            3: 33,
            4: 50,
            5: 67,
            6: 83,
            7: 100,
        }

        for (
            rula_score,
            postguard_score,
        ) in expected.items():

            self.assertEqual(
                modified_rula_to_postguard_score(
                    rula_score
                ),
                postguard_score,
            )

    def test_neutral_posture_is_score_one(
        self,
    ):
        result = (
            calculate_modified_rula_score(
                build_assessment(),
                build_temporal(),
            )
        )

        self.assertEqual(
            result["status"],
            "COMPLETE",
        )

        self.assertEqual(
            result[
                "modified_rula_score"
            ],
            1,
        )

        self.assertEqual(
            result[
                "postguard_risk_score"
            ],
            0,
        )

    def test_flexion_15_degrees_is_neck_score_two(
        self,
    ):
        assessment = build_assessment(
            neck_flexion_status="FLEXION",
            neck_flexion_angle=15.0,
        )

        temporal = build_temporal(
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=10.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "components"
            ][
                "neck_base"
            ][
                "score"
            ],
            2,
        )

        self.assertEqual(
            result[
                "modified_rula_score"
            ],
            2,
        )

    def test_flexion_over_20_is_neck_score_three(
        self,
    ):
        assessment = build_assessment(
            neck_flexion_status="FLEXION",
            neck_flexion_angle=25.0,
        )

        temporal = build_temporal(
            neck_flexion_factor="FLEXION",
            neck_flexion_seconds=10.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "components"
            ][
                "neck_base"
            ][
                "score"
            ],
            3,
        )

    def test_extension_is_neck_score_four(
        self,
    ):
        assessment = build_assessment(
            neck_flexion_status="EXTENSION",
            neck_flexion_angle=-15.0,
        )

        temporal = build_temporal(
            neck_flexion_factor="EXTENSION",
            neck_flexion_seconds=10.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "components"
            ][
                "neck_base"
            ][
                "score"
            ],
            4,
        )

    def test_neck_side_bending_adds_one(
        self,
    ):
        assessment = build_assessment(
            neck_lateral_status="TILT_LEFT",
            neck_lateral_angle=8.0,
        )

        temporal = build_temporal(
            neck_lateral_factor="TILT_LEFT",
            neck_lateral_seconds=10.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "components"
            ][
                "neck_side_bending"
            ][
                "score"
            ],
            1,
        )

        self.assertEqual(
            result[
                "modified_rula_score"
            ],
            2,
        )

    def test_shoulder_asymmetry_adds_one(
        self,
    ):
        assessment = build_assessment(
            shoulder_status="RIGHT_SHOULDER_HIGH",
            shoulder_angle=6.0,
        )

        temporal = build_temporal(
            shoulder_factor=(
                "RIGHT_SHOULDER_HIGH"
            ),
            shoulder_seconds=10.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "components"
            ][
                "shoulder_asymmetry"
            ][
                "score"
            ],
            1,
        )

    def test_sustained_posture_requires_60_seconds(
        self,
    ):
        assessment = build_assessment(
            shoulder_status="RIGHT_SHOULDER_HIGH",
            shoulder_angle=6.0,
        )

        before = (
            calculate_modified_rula_score(
                assessment,
                build_temporal(
                    shoulder_factor=(
                        "RIGHT_SHOULDER_HIGH"
                    ),
                    shoulder_seconds=59.999,
                ),
            )
        )

        self.assertEqual(
            before[
                "components"
            ][
                "sustained_posture"
            ][
                "score"
            ],
            0,
        )

        at_boundary = (
            calculate_modified_rula_score(
                assessment,
                build_temporal(
                    shoulder_factor=(
                        "RIGHT_SHOULDER_HIGH"
                    ),
                    shoulder_seconds=60.0,
                ),
            )
        )

        self.assertEqual(
            at_boundary[
                "components"
            ][
                "sustained_posture"
            ][
                "score"
            ],
            1,
        )

    def test_multiple_sustained_features_only_add_one(
        self,
    ):
        assessment = build_assessment(
            shoulder_status="RIGHT_SHOULDER_HIGH",
            shoulder_angle=6.0,

            neck_lateral_status="TILT_LEFT",
            neck_lateral_angle=8.0,

            neck_flexion_status="FLEXION",
            neck_flexion_angle=25.0,
        )

        temporal = build_temporal(
            shoulder_factor=(
                "RIGHT_SHOULDER_HIGH"
            ),
            shoulder_seconds=70.0,

            neck_lateral_factor=(
                "TILT_LEFT"
            ),
            neck_lateral_seconds=70.0,

            neck_flexion_factor=(
                "FLEXION"
            ),
            neck_flexion_seconds=70.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        # Neck 3
        # Side bend +1
        # Shoulder +1
        # Sustained +1
        #
        # Total = 6, NOT 8.
        self.assertEqual(
            result[
                "modified_rula_score"
            ],
            6,
        )

        self.assertEqual(
            result[
                "components"
            ][
                "sustained_posture"
            ][
                "score"
            ],
            1,
        )

    def test_maximum_score_is_seven(
        self,
    ):
        assessment = build_assessment(
            shoulder_status="LEFT_SHOULDER_HIGH",
            shoulder_angle=-5.0,

            neck_lateral_status="TILT_RIGHT",
            neck_lateral_angle=-10.0,

            neck_flexion_status="EXTENSION",
            neck_flexion_angle=-15.0,
        )

        temporal = build_temporal(
            shoulder_factor=(
                "LEFT_SHOULDER_HIGH"
            ),
            shoulder_seconds=60.0,

            neck_lateral_factor=(
                "TILT_RIGHT"
            ),
            neck_lateral_seconds=60.0,

            neck_flexion_factor=(
                "EXTENSION"
            ),
            neck_flexion_seconds=60.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result[
                "modified_rula_score"
            ],
            7,
        )

        self.assertEqual(
            result[
                "postguard_risk_score"
            ],
            100,
        )

    def test_partial_assessment_does_not_invent_score(
        self,
    ):
        assessment = build_assessment()

        assessment[
            "features"
        ][
            "shoulder_tilt"
        ][
            "evaluated"
        ] = False

        assessment[
            "features"
        ][
            "shoulder_tilt"
        ][
            "reason"
        ] = "TEST_MISSING"

        result = (
            calculate_modified_rula_score(
                assessment,
                build_temporal(),
            )
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

        self.assertIsNone(
            result[
                "modified_rula_score"
            ]
        )

        self.assertIsNone(
            result[
                "postguard_risk_score"
            ]
        )

    def test_factor_mismatch_does_not_invent_duration_score(
        self,
    ):
        assessment = build_assessment(
            neck_flexion_status="FLEXION",
            neck_flexion_angle=15.0,
        )

        temporal = build_temporal(
            neck_flexion_factor="EXTENSION",
            neck_flexion_seconds=100.0,
        )

        result = (
            calculate_modified_rula_score(
                assessment,
                temporal,
            )
        )

        self.assertEqual(
            result["status"],
            "PARTIAL",
        )

        self.assertIsNone(
            result[
                "modified_rula_score"
            ]
        )

    def test_invalid_score_conversion_rejected(
        self,
    ):
        with self.assertRaises(
            ModifiedRULAError
        ):
            modified_rula_to_postguard_score(
                0
            )

        with self.assertRaises(
            ModifiedRULAError
        ):
            modified_rula_to_postguard_score(
                8
            )


if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )