from __future__ import annotations

from copy import deepcopy

from camera_card.posture_assessment.current_posture_assessment import (
    ASSESSMENT_COMPLETE,
    ASSESSMENT_NOT_EVALUATED,
    ASSESSMENT_PARTIAL,

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
    get_default_assessment_rules,
)


# ============================================================
# TEST COUNTERS
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


# ============================================================
# DETECTION BUILDERS
# ============================================================

def valid_feature(
    value,
):

    return {
        "valid": True,

        "value": value,

        "unit": "deg",

        "reason": "OK",

        "status": (
            "validated_prototype"
        ),
    }


def invalid_feature(
    reason="LANDMARK_MISSING",
):

    return {
        "valid": False,

        "value": None,

        "unit": "deg",

        "reason": reason,

        "status": (
            "validated_prototype"
        ),
    }


def detection_result(
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
            "state": (
                context_state
            ),

            "allow_posture_evaluation": (
                allow
            ),

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
# TEST 1
# DEFAULT RULE VERSION
# ============================================================

def test_default_rules():

    rules = (
        get_default_assessment_rules()
    )

    check(
        "Directional rule version preserved",
        rules[
            "version"
        ]
        ==
        "1.2-directional-prototype",
    )

    check(
        "Shoulder left threshold preserved",
        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "left_high_threshold_deg"
        ]
        ==
        -2.0,
    )

    check(
        "Shoulder right threshold preserved",
        rules[
            "features"
        ][
            "shoulder_tilt"
        ][
            "right_high_threshold_deg"
        ]
        ==
        4.0,
    )

    check(
        "Neck left threshold preserved",
        rules[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "left_tilt_threshold_deg"
        ]
        ==
        5.0,
    )

    check(
        "Neck right threshold preserved",
        rules[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "right_tilt_threshold_deg"
        ]
        ==
        -7.0,
    )


# ============================================================
# TEST 2
# NEUTRAL
# ============================================================

def test_neutral():

    result = assess_current_posture(
        detection_result(
            shoulder=0.0,
            neck=0.0,
            flexion=0.0,
        )
    )

    check(
        "Neutral overall complete",
        result[
            "status"
        ]
        ==
        ASSESSMENT_COMPLETE,
    )

    check(
        "Neutral shoulder",
        result[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        SHOULDER_NEAR_LEVEL,
    )

    check(
        "Neutral neck lateral",
        result[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_LATERAL_NEUTRAL,
    )

    check(
        "Neutral flexion",
        result[
            "features"
        ][
            "neck_flexion"
        ][
            "status"
        ]
        ==
        NECK_FLEXION_NEUTRAL,
    )

    check(
        "Neutral has zero factors",
        result[
            "factor_count"
        ]
        ==
        0,
    )


# ============================================================
# TEST 3
# SHOULDER DIRECTION
# ============================================================

def test_shoulder_direction():

    left = assess_current_posture(
        detection_result(
            shoulder=-2.1,
        )
    )

    right = assess_current_posture(
        detection_result(
            shoulder=4.1,
        )
    )

    check(
        "Left shoulder classification",
        left[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        LEFT_SHOULDER_HIGH,
    )

    check(
        "Right shoulder classification",
        right[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        RIGHT_SHOULDER_HIGH,
    )


# ============================================================
# TEST 4
# SHOULDER EXACT BOUNDARIES
# ============================================================

def test_shoulder_boundaries():

    left = assess_current_posture(
        detection_result(
            shoulder=-2.0,
        )
    )

    right = assess_current_posture(
        detection_result(
            shoulder=4.0,
        )
    )

    check(
        "Exact -2 shoulder remains neutral",
        left[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        SHOULDER_NEAR_LEVEL,
    )

    check(
        "Exact +4 shoulder remains neutral",
        right[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        SHOULDER_NEAR_LEVEL,
    )


# ============================================================
# TEST 5
# NECK LATERAL DIRECTION
# ============================================================

def test_neck_direction():

    left = assess_current_posture(
        detection_result(
            neck=5.1,
        )
    )

    right = assess_current_posture(
        detection_result(
            neck=-7.1,
        )
    )

    check(
        "Neck left classification",
        left[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_TILT_LEFT,
    )

    check(
        "Neck right classification",
        right[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_TILT_RIGHT,
    )


# ============================================================
# TEST 6
# NECK EXACT BOUNDARIES
# ============================================================

def test_neck_boundaries():

    left = assess_current_posture(
        detection_result(
            neck=5.0,
        )
    )

    right = assess_current_posture(
        detection_result(
            neck=-7.0,
        )
    )

    check(
        "Exact +5 neck remains neutral",
        left[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_LATERAL_NEUTRAL,
    )

    check(
        "Exact -7 neck remains neutral",
        right[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_LATERAL_NEUTRAL,
    )


# ============================================================
# TEST 7
# FLEXION / EXTENSION
# ============================================================

def test_flexion_direction():

    flexion = (
        assess_current_posture(
            detection_result(
                flexion=10.1,
            )
        )
    )

    extension = (
        assess_current_posture(
            detection_result(
                flexion=-10.1,
            )
        )
    )

    check(
        "Flexion classification",
        flexion[
            "features"
        ][
            "neck_flexion"
        ][
            "status"
        ]
        ==
        NECK_FLEXION,
    )

    check(
        "Extension classification",
        extension[
            "features"
        ][
            "neck_flexion"
        ][
            "status"
        ]
        ==
        NECK_EXTENSION,
    )


# ============================================================
# TEST 8
# FLEXION BOUNDARIES
# ============================================================

def test_flexion_boundaries():

    positive = (
        assess_current_posture(
            detection_result(
                flexion=10.0,
            )
        )
    )

    negative = (
        assess_current_posture(
            detection_result(
                flexion=-10.0,
            )
        )
    )

    check(
        "Exact +10 flexion neutral",
        positive[
            "features"
        ][
            "neck_flexion"
        ][
            "status"
        ]
        ==
        NECK_FLEXION_NEUTRAL,
    )

    check(
        "Exact -10 extension neutral",
        negative[
            "features"
        ][
            "neck_flexion"
        ][
            "status"
        ]
        ==
        NECK_FLEXION_NEUTRAL,
    )


# ============================================================
# TEST 9
# BOTH SHOULDER + NECK FACTOR
#
# Must preserve BOTH classifications.
# ============================================================

def test_factor_overlap_preserved():

    result = (
        assess_current_posture(
            detection_result(
                shoulder=5.0,
                neck=8.0,
                flexion=0.0,
            )
        )
    )

    check(
        "Overlap shoulder preserved",
        result[
            "features"
        ][
            "shoulder_tilt"
        ][
            "status"
        ]
        ==
        RIGHT_SHOULDER_HIGH,
    )

    check(
        "Overlap neck preserved",
        result[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        NECK_TILT_LEFT,
    )

    check(
        "Overlap still two factors",
        result[
            "factor_count"
        ]
        ==
        2,
    )

    interaction = (
        result[
            "interactions"
        ][
            "interactions"
        ][0]
    )

    check(
        "Interaction geometrically coupled",
        interaction[
            "type"
        ]
        ==
        "GEOMETRICALLY_COUPLED",
    )

    check(
        "Interaction active",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Classification overlap true",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is True,
    )


# ============================================================
# TEST 10
# GEOMETRIC COUPLING EXISTS EVEN WHEN NEUTRAL
# ============================================================

def test_coupling_is_measurement_semantic():

    result = (
        assess_current_posture(
            detection_result(
                shoulder=0.5,
                neck=1.0,
                flexion=0.0,
            )
        )
    )

    interaction = (
        result[
            "interactions"
        ][
            "interactions"
        ][0]
    )

    check(
        "Neutral features still geometrically coupled",
        interaction[
            "active"
        ]
        is True,
    )

    check(
        "Neutral coupling not classification overlap",
        interaction[
            "classification"
        ][
            "classification_overlap"
        ]
        is False,
    )


# ============================================================
# TEST 11
# ONE FEATURE INVALID -> PARTIAL
# ============================================================

def test_partial_feature():

    detection = (
        detection_result()
    )

    detection[
        "features"
    ][
        "neck_lateral_tilt"
    ] = (
        invalid_feature(
            "LANDMARK_MISSING"
        )
    )

    result = (
        assess_current_posture(
            detection
        )
    )

    check(
        "One invalid feature gives PARTIAL",
        result[
            "status"
        ]
        ==
        ASSESSMENT_PARTIAL,
    )

    check(
        "Neck feature not evaluated",
        result[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "status"
        ]
        ==
        STATUS_NOT_EVALUATED,
    )

    check(
        "Invalid reason preserved",
        result[
            "features"
        ][
            "neck_lateral_tilt"
        ][
            "reason"
        ]
        ==
        "LANDMARK_MISSING",
    )

    interaction = (
        result[
            "interactions"
        ][
            "interactions"
        ][0]
    )

    check(
        "Interaction inactive when neck invalid",
        interaction[
            "active"
        ]
        is False,
    )


# ============================================================
# TEST 12
# INVALID CONTEXT
# ============================================================

def test_invalid_context():

    result = (
        assess_current_posture(
            detection_result(
                context_state="TRANSITION",
                allow=False,
            )
        )
    )

    check(
        "Invalid context gives NOT_EVALUATED",
        result[
            "status"
        ]
        ==
        ASSESSMENT_NOT_EVALUATED,
    )

    check(
        "Invalid context evaluable false",
        result[
            "evaluable"
        ]
        is False,
    )

    check(
        "Invalid context zero factors",
        result[
            "factor_count"
        ]
        ==
        0,
    )

    interaction = (
        result[
            "interactions"
        ][
            "interactions"
        ][0]
    )

    check(
        "Invalid context interaction inactive",
        interaction[
            "active"
        ]
        is False,
    )


# ============================================================
# TEST 13
# MISSING FEATURE
# ============================================================

def test_missing_feature():

    detection = (
        detection_result()
    )

    del detection[
        "features"
    ][
        "shoulder_tilt"
    ]

    result = (
        assess_current_posture(
            detection
        )
    )

    check(
        "Missing shoulder gives PARTIAL",
        result[
            "status"
        ]
        ==
        ASSESSMENT_PARTIAL,
    )

    check(
        "Missing shoulder reason preserved",
        result[
            "features"
        ][
            "shoulder_tilt"
        ][
            "reason"
        ]
        ==
        "FEATURE_MISSING",
    )


# ============================================================
# TEST 14
# INVALID UNIT
# ============================================================

def test_invalid_unit():

    detection = (
        detection_result()
    )

    detection[
        "features"
    ][
        "shoulder_tilt"
    ][
        "unit"
    ] = "px"

    result = (
        assess_current_posture(
            detection
        )
    )

    check(
        "Invalid unit gives PARTIAL",
        result[
            "status"
        ]
        ==
        ASSESSMENT_PARTIAL,
    )

    check(
        "Invalid unit reason",
        result[
            "features"
        ][
            "shoulder_tilt"
        ][
            "reason"
        ]
        ==
        "INVALID_UNIT",
    )


# ============================================================
# TEST 15
# INVALID VALUE
# ============================================================

def test_invalid_value():

    detection = (
        detection_result()
    )

    detection[
        "features"
    ][
        "neck_flexion"
    ][
        "value"
    ] = float(
        "nan"
    )

    result = (
        assess_current_posture(
            detection
        )
    )

    check(
        "NaN gives PARTIAL",
        result[
            "status"
        ]
        ==
        ASSESSMENT_PARTIAL,
    )

    check(
        "NaN reason INVALID_VALUE",
        result[
            "features"
        ][
            "neck_flexion"
        ][
            "reason"
        ]
        ==
        "INVALID_VALUE",
    )


# ============================================================
# TEST 16
# RISK / ALERT MUST REMAIN NONE
# ============================================================

def test_no_risk_or_alert():

    result = (
        assess_current_posture(
            detection_result(
                shoulder=6.0,
                neck=9.0,
                flexion=15.0,
            )
        )
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

    interaction = (
        result[
            "interactions"
        ][
            "interactions"
        ][0]
    )

    effects = (
        interaction[
            "effects"
        ]
    )

    check(
        "Interaction cannot change risk",
        effects[
            "changes_risk"
        ]
        is False,
    )

    check(
        "Interaction cannot change alert",
        effects[
            "changes_alert"
        ]
        is False,
    )

    check(
        "Interaction cannot suppress factors",
        effects[
            "suppresses_factor"
        ]
        is False,
    )


# ============================================================
# TEST 17
# SEMANTICS
# ============================================================

def test_semantics():

    result = (
        assess_current_posture(
            detection_result()
        )
    )

    neck_semantics = (
        result[
            "semantics"
        ][
            "neck_lateral_tilt"
        ]
    )

    check(
        "Neck displayed as Relative Neck Lateral Tilt",
        neck_semantics[
            "display_name"
        ]
        ==
        "Relative Neck Lateral Tilt",
    )

    check(
        "Neck formula documented",
        neck_semantics[
            "formula"
        ]
        ==
        "ear_angle - shoulder_angle",
    )


# ============================================================
# TEST 18
# INPUT OBJECT MUST NOT BE MUTATED
# ============================================================

def test_input_not_mutated():

    detection = (
        detection_result(
            shoulder=5.0,
            neck=8.0,
            flexion=11.0,
        )
    )

    before = deepcopy(
        detection
    )

    assess_current_posture(
        detection
    )

    check(
        "Assessment does not mutate DetectionPipeline result",
        detection == before,
    )


# ============================================================
# TEST 19
# UNSUPPORTED DETECTION CONTRACT
# ============================================================

def test_bad_detection_contract():

    detection = (
        detection_result()
    )

    detection[
        "contract_version"
    ] = "99.0"

    raised = False

    try:

        assess_current_posture(
            detection
        )

    except ValueError:

        raised = True

    check(
        "Bad Detection contract rejected",
        raised,
    )


# ============================================================
# TEST 20
# INVALID INPUT TYPE
# ============================================================

def test_bad_input():

    raised = False

    try:

        assess_current_posture(
            None
        )

    except ValueError:

        raised = True

    check(
        "Non-mapping input rejected",
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
    print("=" * 100)

    print(
        "POSTGUARD - CURRENT POSTURE ASSESSMENT "
        "INTERACTION REGRESSION"
    )

    print("=" * 100)

    tests = [
        test_default_rules,
        test_neutral,
        test_shoulder_direction,
        test_shoulder_boundaries,
        test_neck_direction,
        test_neck_boundaries,
        test_flexion_direction,
        test_flexion_boundaries,
        test_factor_overlap_preserved,
        test_coupling_is_measurement_semantic,
        test_partial_feature,
        test_invalid_context,
        test_missing_feature,
        test_invalid_unit,
        test_invalid_value,
        test_no_risk_or_alert,
        test_semantics,
        test_input_not_mutated,
        test_bad_detection_contract,
        test_bad_input,
    ]

    for test in tests:

        print()
        print(
            "-" * 100
        )

        print(
            test.__name__
        )

        test()

    print()
    print("=" * 100)

    print(
        f"PASSED: {PASSED}"
    )

    print(
        f"FAILED: {FAILED}"
    )

    print("=" * 100)

    if FAILED > 0:

        raise AssertionError(
            "Current Posture Assessment "
            "interaction regression failed."
        )

    print()

    print(
        "CURRENT POSTURE ASSESSMENT "
        "INTERACTION REGRESSION: PASSED"
    )


if __name__ == "__main__":

    main()