from __future__ import annotations

import math
import unittest
from copy import deepcopy

from camera_card.posture_assessment.current_posture_assessment import (
    ASSESSMENT_COMPLETE,
    ASSESSMENT_CONTRACT_VERSION,
    ASSESSMENT_NOT_EVALUATED,
    ASSESSMENT_PARTIAL,

    DEFAULT_RULES,

    LEFT_SHOULDER_HIGH,
    NECK_EXTENSION,
    NECK_FLEXION,
    NECK_FLEXION_NEUTRAL,
    NECK_LATERAL_NEUTRAL,
    NECK_TILT_LEFT,
    NECK_TILT_RIGHT,
    RIGHT_SHOULDER_HIGH,
    SHOULDER_NEAR_LEVEL,
    STATUS_NOT_EVALUATED,

    assess_current_posture,
    get_assessment_feature_semantics,
    get_default_assessment_rules,
)


# ============================================================
# TEST HELPERS
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


def make_detection(
    *,
    shoulder=0.0,
    neck=0.0,
    flexion=0.0,
    context_state="VALID",
    allow=True,
):
    return {
        "contract_version": "1.0",

        "timestamp": 123.456,

        "context": {
            "state": context_state,
            "allow_posture_evaluation": allow,
            "reason": "TEST",
            "stable_seconds": 2.0,
        },

        "features": {
            "shoulder_tilt": valid_feature(
                shoulder
            ),

            "neck_lateral_tilt": valid_feature(
                neck
            ),

            "neck_flexion": valid_feature(
                flexion
            ),
        },
    }


# ============================================================
# TEST CLASS
# ============================================================

class TestCurrentPostureAssessment(
    unittest.TestCase
):

    # ========================================================
    # CONTRACT
    # ========================================================

    def test_assessment_contract_version(self):

        result = assess_current_posture(
            make_detection()
        )

        self.assertEqual(
            result[
                "contract_version"
            ],
            ASSESSMENT_CONTRACT_VERSION,
        )

        self.assertEqual(
            result[
                "source_contract_version"
            ],
            "1.0",
        )


    def test_rules_version(self):

        rules = (
            get_default_assessment_rules()
        )

        self.assertEqual(
            rules[
                "version"
            ],
            "1.2-directional-prototype",
        )


    # ========================================================
    # DEFAULT RULES
    # ========================================================

    def test_default_shoulder_thresholds(self):

        rule = (
            DEFAULT_RULES[
                "features"
            ][
                "shoulder_tilt"
            ]
        )

        self.assertEqual(
            rule[
                "left_high_threshold_deg"
            ],
            -2.0,
        )

        self.assertEqual(
            rule[
                "right_high_threshold_deg"
            ],
            4.0,
        )


    def test_default_neck_lateral_thresholds(self):

        rule = (
            DEFAULT_RULES[
                "features"
            ][
                "neck_lateral_tilt"
            ]
        )

        self.assertEqual(
            rule[
                "left_tilt_threshold_deg"
            ],
            5.0,
        )

        self.assertEqual(
            rule[
                "right_tilt_threshold_deg"
            ],
            -7.0,
        )


    def test_default_flexion_thresholds(self):

        rule = (
            DEFAULT_RULES[
                "features"
            ][
                "neck_flexion"
            ]
        )

        self.assertEqual(
            rule[
                "flexion_threshold_deg"
            ],
            10.0,
        )

        self.assertEqual(
            rule[
                "extension_threshold_deg"
            ],
            -10.0,
        )


    # ========================================================
    # NEUTRAL
    # ========================================================

    def test_all_neutral_is_complete(self):

        result = assess_current_posture(
            make_detection(
                shoulder=0.0,
                neck=0.0,
                flexion=0.0,
            )
        )

        self.assertEqual(
            result["status"],
            ASSESSMENT_COMPLETE,
        )

        self.assertTrue(
            result["evaluable"]
        )

        self.assertEqual(
            result[
                "factor_count"
            ],
            0,
        )


    def test_neutral_feature_states(self):

        result = assess_current_posture(
            make_detection()
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            SHOULDER_NEAR_LEVEL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_LATERAL_NEUTRAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_FLEXION_NEUTRAL,
        )


    # ========================================================
    # SHOULDER
    # ========================================================

    def test_left_shoulder_high(self):

        result = assess_current_posture(
            make_detection(
                shoulder=-2.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            LEFT_SHOULDER_HIGH,
        )


    def test_right_shoulder_high(self):

        result = assess_current_posture(
            make_detection(
                shoulder=4.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            RIGHT_SHOULDER_HIGH,
        )


    def test_shoulder_left_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                shoulder=-2.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            SHOULDER_NEAR_LEVEL,
        )


    def test_shoulder_right_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                shoulder=4.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            SHOULDER_NEAR_LEVEL,
        )


    # ========================================================
    # RELATIVE NECK LATERAL
    # ========================================================

    def test_neck_tilt_left(self):

        result = assess_current_posture(
            make_detection(
                neck=5.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_TILT_LEFT,
        )


    def test_neck_tilt_right(self):

        result = assess_current_posture(
            make_detection(
                neck=-7.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_TILT_RIGHT,
        )


    def test_neck_left_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                neck=5.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_LATERAL_NEUTRAL,
        )


    def test_neck_right_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                neck=-7.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ][
                "status"
            ],
            NECK_LATERAL_NEUTRAL,
        )


    # ========================================================
    # FLEXION / EXTENSION
    # ========================================================

    def test_neck_flexion(self):

        result = assess_current_posture(
            make_detection(
                flexion=10.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_FLEXION,
        )


    def test_neck_extension(self):

        result = assess_current_posture(
            make_detection(
                flexion=-10.01
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_EXTENSION,
        )


    def test_flexion_exact_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                flexion=10.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_FLEXION_NEUTRAL,
        )


    def test_extension_exact_boundary_is_neutral(self):

        result = assess_current_posture(
            make_detection(
                flexion=-10.0
            )
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "status"
            ],
            NECK_FLEXION_NEUTRAL,
        )


    # ========================================================
    # MULTIPLE FACTORS
    # ========================================================

    def test_multiple_factors_are_preserved(self):

        result = assess_current_posture(
            make_detection(
                shoulder=5.0,
                neck=8.0,
                flexion=15.0,
            )
        )

        self.assertEqual(
            result[
                "factor_count"
            ],
            3,
        )

        factors = {
            item["feature"]:
            item["factor"]

            for item
            in result["factors"]
        }

        self.assertEqual(
            factors[
                "shoulder_tilt"
            ],
            RIGHT_SHOULDER_HIGH,
        )

        self.assertEqual(
            factors[
                "neck_lateral_tilt"
            ],
            NECK_TILT_LEFT,
        )

        self.assertEqual(
            factors[
                "neck_flexion"
            ],
            NECK_FLEXION,
        )


    # ========================================================
    # INTERACTION CONTRACT
    # ========================================================

    def test_shoulder_neck_are_geometrically_coupled(self):

        result = assess_current_posture(
            make_detection(
                shoulder=0.0,
                neck=0.0,
            )
        )

        interaction = (
            result[
                "interactions"
            ][
                "interactions"
            ][0]
        )

        self.assertEqual(
            interaction[
                "type"
            ],
            "GEOMETRICALLY_COUPLED",
        )

        self.assertTrue(
            interaction[
                "active"
            ]
        )


    def test_neutral_interaction_has_no_overlap(self):

        result = assess_current_posture(
            make_detection()
        )

        interaction = (
            result[
                "interactions"
            ][
                "interactions"
            ][0]
        )

        self.assertFalse(
            interaction[
                "classification"
            ][
                "classification_overlap"
            ]
        )


    def test_both_factors_have_classification_overlap(self):

        result = assess_current_posture(
            make_detection(
                shoulder=5.0,
                neck=8.0,
            )
        )

        interaction = (
            result[
                "interactions"
            ][
                "interactions"
            ][0]
        )

        self.assertTrue(
            interaction[
                "classification"
            ][
                "classification_overlap"
            ]
        )


    def test_overlap_does_not_suppress_factors(self):

        result = assess_current_posture(
            make_detection(
                shoulder=5.0,
                neck=8.0,
            )
        )

        self.assertEqual(
            result[
                "factor_count"
            ],
            2,
        )

        effects = (
            result[
                "interactions"
            ][
                "interactions"
            ][0][
                "effects"
            ]
        )

        self.assertFalse(
            effects[
                "suppresses_factor"
            ]
        )

        self.assertFalse(
            effects[
                "changes_classification"
            ]
        )


    # ========================================================
    # PARTIAL FEATURE
    # ========================================================

    def test_invalid_single_feature_is_partial(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "neck_lateral_tilt"
        ] = invalid_feature(
            "LANDMARK_MISSING"
        )

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_PARTIAL,
        )

        self.assertEqual(
            result[
                "evaluated_feature_count"
            ],
            2,
        )

        self.assertEqual(
            result[
                "not_evaluated_feature_count"
            ],
            1,
        )


    def test_invalid_reason_is_preserved(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "neck_lateral_tilt"
        ] = invalid_feature(
            "LANDMARK_MISSING"
        )

        result = assess_current_posture(
            detection
        )

        feature = (
            result[
                "features"
            ][
                "neck_lateral_tilt"
            ]
        )

        self.assertEqual(
            feature["status"],
            STATUS_NOT_EVALUATED,
        )

        self.assertEqual(
            feature["reason"],
            "LANDMARK_MISSING",
        )


    def test_interaction_inactive_when_neck_invalid(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "neck_lateral_tilt"
        ] = invalid_feature()

        result = assess_current_posture(
            detection
        )

        interaction = (
            result[
                "interactions"
            ][
                "interactions"
            ][0]
        )

        self.assertFalse(
            interaction[
                "active"
            ]
        )

        self.assertEqual(
            interaction[
                "type"
            ],
            "NOT_EVALUATED",
        )


    # ========================================================
    # MISSING FEATURE
    # ========================================================

    def test_missing_feature_is_partial(self):

        detection = make_detection()

        del detection[
            "features"
        ][
            "shoulder_tilt"
        ]

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result["status"],
            ASSESSMENT_PARTIAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "reason"
            ],
            "FEATURE_MISSING",
        )


    # ========================================================
    # FEATURES MAPPING MISSING
    # ========================================================

    def test_features_missing_is_not_evaluated(self):

        detection = make_detection()

        detection.pop(
            "features"
        )

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )

        self.assertEqual(
            result[
                "evaluated_feature_count"
            ],
            0,
        )


    # ========================================================
    # INVALID UNIT
    # ========================================================

    def test_invalid_unit_is_partial(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "shoulder_tilt"
        ][
            "unit"
        ] = "px"

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_PARTIAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "reason"
            ],
            "INVALID_UNIT",
        )


    # ========================================================
    # INVALID VALUES
    # ========================================================

    def test_nan_is_not_evaluated(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "neck_flexion"
        ][
            "value"
        ] = float("nan")

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_PARTIAL,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "reason"
            ],
            "INVALID_VALUE",
        )


    def test_infinity_is_not_evaluated(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "neck_flexion"
        ][
            "value"
        ] = math.inf

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "features"
            ][
                "neck_flexion"
            ][
                "reason"
            ],
            "INVALID_VALUE",
        )


    def test_boolean_is_not_valid_number(self):

        detection = make_detection()

        detection[
            "features"
        ][
            "shoulder_tilt"
        ][
            "value"
        ] = True

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "reason"
            ],
            "INVALID_VALUE",
        )


    # ========================================================
    # CONTEXT
    # ========================================================

    def test_transition_context_not_evaluated(self):

        result = assess_current_posture(
            make_detection(
                context_state="TRANSITION",
                allow=False,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )

        self.assertFalse(
            result[
                "evaluable"
            ]
        )

        self.assertEqual(
            result[
                "factor_count"
            ],
            0,
        )


    def test_unknown_context_not_evaluated(self):

        result = assess_current_posture(
            make_detection(
                context_state="UNKNOWN",
                allow=False,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )


    def test_valid_context_but_allow_false_not_evaluated(self):

        result = assess_current_posture(
            make_detection(
                context_state="VALID",
                allow=False,
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )

        self.assertEqual(
            result[
                "reason"
            ],
            "POSTURE_EVALUATION_NOT_ALLOWED",
        )


    def test_missing_context_not_evaluated(self):

        detection = make_detection()

        detection.pop(
            "context"
        )

        result = assess_current_posture(
            detection
        )

        self.assertEqual(
            result[
                "status"
            ],
            ASSESSMENT_NOT_EVALUATED,
        )

        self.assertEqual(
            result[
                "reason"
            ],
            "CONTEXT_MISSING",
        )


    # ========================================================
    # RISK / ALERT
    # ========================================================

    def test_risk_and_alert_remain_none(self):

        result = assess_current_posture(
            make_detection(
                shoulder=6.0,
                neck=8.0,
                flexion=15.0,
            )
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
    # SEMANTICS
    # ========================================================

    def test_neck_semantics_are_relative(self):

        semantics = (
            get_assessment_feature_semantics()
        )

        neck = semantics[
            "neck_lateral_tilt"
        ]

        self.assertEqual(
            neck[
                "display_name"
            ],
            "Relative Neck Lateral Tilt",
        )

        self.assertEqual(
            neck[
                "formula"
            ],
            "ear_angle - shoulder_angle",
        )


    def test_semantics_are_in_result(self):

        result = assess_current_posture(
            make_detection()
        )

        self.assertIn(
            "semantics",
            result,
        )

        self.assertIn(
            "neck_lateral_tilt",
            result[
                "semantics"
            ],
        )


    # ========================================================
    # IMMUTABILITY
    # ========================================================

    def test_detection_result_not_mutated(self):

        detection = make_detection(
            shoulder=5.0,
            neck=8.0,
            flexion=12.0,
        )

        before = deepcopy(
            detection
        )

        assess_current_posture(
            detection
        )

        self.assertEqual(
            detection,
            before,
        )


    def test_default_rules_copy_is_independent(self):

        first = (
            get_default_assessment_rules()
        )

        first[
            "features"
        ][
            "shoulder_tilt"
        ][
            "right_high_threshold_deg"
        ] = 999.0

        second = (
            get_default_assessment_rules()
        )

        self.assertEqual(
            second[
                "features"
            ][
                "shoulder_tilt"
            ][
                "right_high_threshold_deg"
            ],
            4.0,
        )


    # ========================================================
    # CUSTOM RULE VALIDATION
    # ========================================================

    def test_custom_directional_rules_work(self):

        rules = (
            get_default_assessment_rules()
        )

        rules[
            "version"
        ] = "custom-test"

        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "right_high_threshold_deg"
        ] = 6.0

        result = assess_current_posture(
            make_detection(
                shoulder=5.0
            ),
            rules=rules,
        )

        self.assertEqual(
            result[
                "features"
            ][
                "shoulder_tilt"
            ][
                "status"
            ],
            SHOULDER_NEAR_LEVEL,
        )

        self.assertEqual(
            result[
                "rules_version"
            ],
            "custom-test",
        )


    def test_bad_rule_unit_raises(self):

        rules = (
            get_default_assessment_rules()
        )

        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "unit"
        ] = "px"

        with self.assertRaises(
            ValueError
        ):

            assess_current_posture(
                make_detection(),
                rules=rules,
            )


    def test_missing_rule_raises(self):

        rules = (
            get_default_assessment_rules()
        )

        del rules[
            "features"
        ][
            "neck_lateral_tilt"
        ]

        with self.assertRaises(
            ValueError
        ):

            assess_current_posture(
                make_detection(),
                rules=rules,
            )


    def test_invalid_threshold_order_raises(self):

        rules = (
            get_default_assessment_rules()
        )

        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "left_high_threshold_deg"
        ] = 5.0

        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "right_high_threshold_deg"
        ] = 4.0

        with self.assertRaises(
            ValueError
        ):

            assess_current_posture(
                make_detection(),
                rules=rules,
            )


    # ========================================================
    # DETECTION CONTRACT
    # ========================================================

    def test_unsupported_detection_contract_raises(self):

        detection = make_detection()

        detection[
            "contract_version"
        ] = "99.0"

        with self.assertRaises(
            ValueError
        ):

            assess_current_posture(
                detection
            )


    def test_non_mapping_input_raises(self):

        with self.assertRaises(
            ValueError
        ):

            assess_current_posture(
                None
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    unittest.main(
        verbosity=2
    )