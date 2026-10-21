from __future__ import annotations

from camera_card.posture_assessment.assessment_interaction import (
    INTERACTION_CONTRACT_VERSION,
    INTERACTION_GEOMETRICALLY_COUPLED,
    INTERACTION_NOT_EVALUATED,
    build_assessment_interactions,
)


# ============================================================
# SIMPLE ASSERT HELPERS
# ============================================================

PASSED = 0
FAILED = 0


def check(
    name,
    condition,
):

    global PASSED
    global FAILED

    if condition:

        PASSED += 1

        print(
            f"[PASS] {name}"
        )

    else:

        FAILED += 1

        print(
            f"[FAIL] {name}"
        )


def evaluated_feature(
    *,
    status,
    current,
    is_factor,
):

    return {
        "feature": "test",

        "status": status,

        "reason": "RULE_MATCH",

        "current": current,

        "absolute_current": (
            abs(current)
        ),

        "unit": "deg",

        "evaluated": True,

        "is_posture_factor": (
            is_factor
        ),
    }


def not_evaluated_feature():

    return {
        "feature": "test",

        "status": "NOT_EVALUATED",

        "reason": "FEATURE_INVALID",

        "current": None,

        "absolute_current": None,

        "unit": "deg",

        "evaluated": False,

        "is_posture_factor": False,
    }


# ============================================================
# TEST 1
# BOTH NEUTRAL
# ============================================================

def test_both_neutral():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="NEAR_LEVEL",
                current=0.5,
                is_factor=False,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="NEUTRAL",
                current=1.0,
                is_factor=False,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Contract version",
        result[
            "contract_version"
        ]
        ==
        INTERACTION_CONTRACT_VERSION,
    )

    check(
        "Neutral pair is geometrically coupled",
        interaction[
            "type"
        ]
        ==
        INTERACTION_GEOMETRICALLY_COUPLED,
    )

    check(
        "Neutral pair interaction active",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Neutral pair no classification overlap",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is False,
    )


# ============================================================
# TEST 2
# BOTH POSTURE FACTORS
# ============================================================

def test_both_factors():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="RIGHT_SHOULDER_HIGH",
                current=5.0,
                is_factor=True,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="TILT_LEFT",
                current=8.0,
                is_factor=True,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Both factor interaction stays active",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Both factor overlap detected",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is True,
    )

    check(
        "Shoulder status preserved",
        interaction[
            "classification"
        ][
            "shoulder_status"
        ]
        ==
        "RIGHT_SHOULDER_HIGH",
    )

    check(
        "Neck status preserved",
        interaction[
            "classification"
        ][
            "neck_lateral_status"
        ]
        ==
        "TILT_LEFT",
    )


# ============================================================
# TEST 3
# SHOULDER FACTOR ONLY
# ============================================================

def test_shoulder_factor_only():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="LEFT_SHOULDER_HIGH",
                current=-3.0,
                is_factor=True,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="NEUTRAL",
                current=2.0,
                is_factor=False,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Shoulder-only still geometrically coupled",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Shoulder-only not classification overlap",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is False,
    )


# ============================================================
# TEST 4
# NECK FACTOR ONLY
# ============================================================

def test_neck_factor_only():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="NEAR_LEVEL",
                current=1.0,
                is_factor=False,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="TILT_RIGHT",
                current=-8.0,
                is_factor=True,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Neck-only still geometrically coupled",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Neck-only not classification overlap",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is False,
    )


# ============================================================
# TEST 5
# SHOULDER NOT EVALUATED
# ============================================================

def test_shoulder_not_evaluated():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            not_evaluated_feature()
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="TILT_LEFT",
                current=8.0,
                is_factor=True,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Missing shoulder disables interaction",
        interaction[
            "active"
        ]
        is False,
    )

    check(
        "Missing shoulder interaction not evaluated",
        interaction[
            "type"
        ]
        ==
        INTERACTION_NOT_EVALUATED,
    )


# ============================================================
# TEST 6
# NECK NOT EVALUATED
# ============================================================

def test_neck_not_evaluated():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="RIGHT_SHOULDER_HIGH",
                current=5.0,
                is_factor=True,
            )
        ),

        "neck_lateral_tilt": (
            not_evaluated_feature()
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Missing neck disables interaction",
        interaction[
            "active"
        ]
        is False,
    )

    check(
        "Missing neck interaction not evaluated",
        interaction[
            "type"
        ]
        ==
        INTERACTION_NOT_EVALUATED,
    )


# ============================================================
# TEST 7
# BOTH NOT EVALUATED
# ============================================================

def test_both_not_evaluated():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            not_evaluated_feature()
        ),

        "neck_lateral_tilt": (
            not_evaluated_feature()
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Both invalid interaction inactive",
        interaction[
            "active"
        ]
        is False,
    )

    check(
        "Both invalid overlap false",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is False,
    )


# ============================================================
# TEST 8
# MISSING FEATURE KEY
# ============================================================

def test_missing_feature():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="NEAR_LEVEL",
                current=0.0,
                is_factor=False,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    check(
        "Missing feature key handled",
        interaction[
            "active"
        ]
        is False,
    )


# ============================================================
# TEST 9
# CONTRACT MUST NOT CHANGE DOWNSTREAM LAYERS
# ============================================================

def test_no_downstream_effects():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="RIGHT_SHOULDER_HIGH",
                current=5.5,
                is_factor=True,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="TILT_LEFT",
                current=8.0,
                is_factor=True,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    effects = (
        interaction[
            "effects"
        ]
    )

    check(
        "Does not change classification",
        effects[
            "changes_classification"
        ]
        is False,
    )

    check(
        "Does not suppress factor",
        effects[
            "suppresses_factor"
        ]
        is False,
    )

    check(
        "Does not change threshold",
        effects[
            "changes_threshold"
        ]
        is False,
    )

    check(
        "Does not change Gate",
        effects[
            "changes_measurement_change_gate"
        ]
        is False,
    )

    check(
        "Does not change risk",
        effects[
            "changes_risk"
        ]
        is False,
    )

    check(
        "Does not change alert",
        effects[
            "changes_alert"
        ]
        is False,
    )

    check(
        "Does not change Temporal Tracking",
        effects[
            "changes_temporal_tracking"
        ]
        is False,
    )

    check(
        "Risk remains None",
        result[
            "risk"
        ]
        is None,
    )

    check(
        "Alert remains None",
        result[
            "alert"
        ]
        is None,
    )


# ============================================================
# TEST 10
# INTERPRETATION SEMANTICS
# ============================================================

def test_interpretation_semantics():

    result = build_assessment_interactions({
        "shoulder_tilt": (
            evaluated_feature(
                status="RIGHT_SHOULDER_HIGH",
                current=5.0,
                is_factor=True,
            )
        ),

        "neck_lateral_tilt": (
            evaluated_feature(
                status="TILT_LEFT",
                current=8.0,
                is_factor=True,
            )
        ),
    })

    interaction = (
        result[
            "interactions"
        ][0]
    )

    interpretation = (
        interaction[
            "interpretation"
        ]
    )

    check(
        "Classification preserved",
        interpretation[
            "classification_preserved"
        ]
        is True,
    )

    check(
        "Measurement not invalidated",
        interpretation[
            "measurement_invalidated"
        ]
        is False,
    )

    check(
        "No measurement error implied",
        interpretation[
            "measurement_error_implied"
        ]
        is False,
    )

    check(
        "No physical cause inferred",
        interpretation[
            "physical_cause_inferred"
        ]
        is False,
    )

    check(
        "No medical meaning",
        interpretation[
            "medical_meaning"
        ]
        is False,
    )

    check(
        "No risk meaning",
        interpretation[
            "risk_meaning"
        ]
        is False,
    )


# ============================================================
# INPUT VALIDATION
# ============================================================

def test_invalid_input():

    raised = False

    try:

        build_assessment_interactions(
            None
        )

    except ValueError:
        raised = True

    check(
        "Invalid input raises ValueError",
        raised,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global PASSED
    global FAILED

    PASSED = 0
    FAILED = 0

    print()
    print("=" * 90)

    print(
        "POSTGUARD - ASSESSMENT INTERACTION CONTRACT TEST"
    )

    print("=" * 90)

    tests = [
        test_both_neutral,
        test_both_factors,
        test_shoulder_factor_only,
        test_neck_factor_only,
        test_shoulder_not_evaluated,
        test_neck_not_evaluated,
        test_both_not_evaluated,
        test_missing_feature,
        test_no_downstream_effects,
        test_interpretation_semantics,
        test_invalid_input,
    ]

    for test in tests:

        print()

        test()

    print()
    print("=" * 90)

    print(
        f"PASSED: {PASSED}"
    )

    print(
        f"FAILED: {FAILED}"
    )

    print("=" * 90)

    if FAILED > 0:

        raise AssertionError(
            (
                "Assessment Interaction "
                "Contract test failed."
            )
        )

    print()
    print(
        "ASSESSMENT INTERACTION CONTRACT: PASSED"
    )


if __name__ == "__main__":
    main()