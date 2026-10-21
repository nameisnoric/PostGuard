from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping

from camera_card.posture_assessment.assessment_interaction import (
    build_assessment_interactions,
)


# ============================================================
# CONTRACT
# ============================================================

ASSESSMENT_CONTRACT_VERSION = "1.1"
EXPECTED_DETECTION_CONTRACT_VERSION = "1.0"


# ============================================================
# CONTEXT
# ============================================================

CONTEXT_VALID = "VALID"


# ============================================================
# OVERALL ASSESSMENT STATES
# ============================================================

ASSESSMENT_COMPLETE = "COMPLETE"
ASSESSMENT_PARTIAL = "PARTIAL"
ASSESSMENT_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# FEATURE STATE
# ============================================================

STATUS_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# SHOULDER STATES
# ============================================================

SHOULDER_NEAR_LEVEL = "NEAR_LEVEL"
LEFT_SHOULDER_HIGH = "LEFT_SHOULDER_HIGH"
RIGHT_SHOULDER_HIGH = "RIGHT_SHOULDER_HIGH"


# ============================================================
# NECK LATERAL STATES
# ============================================================

NECK_LATERAL_NEUTRAL = "NEUTRAL"
NECK_TILT_LEFT = "TILT_LEFT"
NECK_TILT_RIGHT = "TILT_RIGHT"


# ============================================================
# NECK FLEXION STATES
# ============================================================

NECK_FLEXION_NEUTRAL = "NEUTRAL"
NECK_FLEXION = "FLEXION"
NECK_EXTENSION = "EXTENSION"


# ============================================================
# DEFAULT DIRECTIONAL PROTOTYPE RULES
#
# IMPORTANT
#
# These thresholds are:
#
# - prototype engineering classification thresholds
#
# They are NOT:
#
# - medical thresholds
# - clinical thresholds
# - RULA thresholds
# - risk thresholds
# - Measurement-Change Gate thresholds
#
# Boundary rule:
#
# exact threshold == neutral
#
# because classification uses strict < and >
# ============================================================

DEFAULT_RULES = {
    "version": "1.2-directional-prototype",

    "features": {
        "shoulder_tilt": {
            "left_high_threshold_deg": -2.0,
            "right_high_threshold_deg": 4.0,
            "unit": "deg",
        },

        "neck_lateral_tilt": {
            "left_tilt_threshold_deg": 5.0,
            "right_tilt_threshold_deg": -7.0,
            "unit": "deg",
        },

        "neck_flexion": {
            "flexion_threshold_deg": 10.0,
            "extension_threshold_deg": -10.0,
            "unit": "deg",
        },
    },
}


# ============================================================
# REQUIRED FEATURES
# ============================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
)


EXPECTED_UNITS = {
    "shoulder_tilt": "deg",
    "neck_lateral_tilt": "deg",
    "neck_flexion": "deg",
}


# ============================================================
# SEMANTICS
#
# IMPORTANT:
#
# neck_lateral_tilt is RELATIVE.
#
# It is NOT:
#
#     absolute head tilt relative to the image horizon
#
# It is:
#
#     ear/head line angle
#     relative to
#     shoulder line angle
#
# Formula in DetectionPipeline:
#
#     neck_lateral_tilt
#     =
#     ear_angle - shoulder_angle
# ============================================================

FEATURE_SEMANTICS = {
    "shoulder_tilt": {
        "display_name": "Shoulder Tilt",

        "meaning": (
            "Image-space angle of the shoulder line "
            "according to the DetectionPipeline definition."
        ),

        "sign_convention": {
            "negative": "LEFT_SHOULDER_HIGH_DIRECTION",
            "positive": "RIGHT_SHOULDER_HIGH_DIRECTION",
        },

        "unit": "deg",
    },

    "neck_lateral_tilt": {
        "display_name": "Relative Neck Lateral Tilt",

        "meaning": (
            "Relative lateral angle of the ear/head line "
            "with respect to the shoulder line."
        ),

        "formula": (
            "ear_angle - shoulder_angle"
        ),

        "sign_convention": {
            "positive": "TILT_LEFT_DIRECTION",
            "negative": "TILT_RIGHT_DIRECTION",
        },

        "unit": "deg",
    },

    "neck_flexion": {
        "display_name": "Neck Flexion",

        "meaning": (
            "PostGuard prototype neck flexion/extension "
            "measurement."
        ),

        "sign_convention": {
            "positive": "FLEXION_DIRECTION",
            "negative": "EXTENSION_DIRECTION",
        },

        "unit": "deg",
    },
}


# ============================================================
# NUMERIC VALIDATION
# ============================================================

def _finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    # bool is subclass of int in Python.
    if isinstance(
        value,
        bool,
    ):
        return None

    if not isinstance(
        value,
        (int, float),
    ):
        return None

    number = float(
        value
    )

    if not math.isfinite(
        number
    ):
        return None

    return number


# ============================================================
# RULE VALIDATION HELPERS
# ============================================================

def _required_threshold(
    rule: Mapping[str, Any],
    key: str,
    feature_name: str,
) -> float:

    value = _finite_number(
        rule.get(
            key
        )
    )

    if value is None:

        raise ValueError(
            f"Invalid {key} "
            f"for {feature_name}"
        )

    return value


# ============================================================
# RULE VALIDATION
# ============================================================

def _validate_rules(
    rules: Mapping[str, Any],
) -> dict[str, Any]:

    if not isinstance(
        rules,
        Mapping,
    ):

        raise ValueError(
            "rules must be a mapping"
        )

    feature_rules = rules.get(
        "features"
    )

    if not isinstance(
        feature_rules,
        Mapping,
    ):

        raise ValueError(
            "rules.features must be a mapping"
        )

    normalized = {
        "version": str(
            rules.get(
                "version",
                "unknown",
            )
        ),

        "features": {},
    }

    # ========================================================
    # SHOULDER
    # ========================================================

    shoulder_rule = feature_rules.get(
        "shoulder_tilt"
    )

    if not isinstance(
        shoulder_rule,
        Mapping,
    ):

        raise ValueError(
            "Missing assessment rule for shoulder_tilt"
        )

    if (
        shoulder_rule.get(
            "unit"
        )
        !=
        "deg"
    ):

        raise ValueError(
            "Invalid rule unit for shoulder_tilt"
        )

    shoulder_left = _required_threshold(
        shoulder_rule,
        "left_high_threshold_deg",
        "shoulder_tilt",
    )

    shoulder_right = _required_threshold(
        shoulder_rule,
        "right_high_threshold_deg",
        "shoulder_tilt",
    )

    if shoulder_left >= shoulder_right:

        raise ValueError(
            "shoulder_tilt directional thresholds "
            "must satisfy left < right"
        )

    normalized[
        "features"
    ][
        "shoulder_tilt"
    ] = {
        "left_high_threshold_deg": (
            shoulder_left
        ),

        "right_high_threshold_deg": (
            shoulder_right
        ),

        "unit": "deg",
    }

    # ========================================================
    # NECK LATERAL
    # ========================================================

    neck_rule = feature_rules.get(
        "neck_lateral_tilt"
    )

    if not isinstance(
        neck_rule,
        Mapping,
    ):

        raise ValueError(
            "Missing assessment rule for neck_lateral_tilt"
        )

    if (
        neck_rule.get(
            "unit"
        )
        !=
        "deg"
    ):

        raise ValueError(
            "Invalid rule unit for neck_lateral_tilt"
        )

    neck_left = _required_threshold(
        neck_rule,
        "left_tilt_threshold_deg",
        "neck_lateral_tilt",
    )

    neck_right = _required_threshold(
        neck_rule,
        "right_tilt_threshold_deg",
        "neck_lateral_tilt",
    )

    if neck_right >= neck_left:

        raise ValueError(
            "neck_lateral_tilt directional thresholds "
            "must satisfy right < left"
        )

    normalized[
        "features"
    ][
        "neck_lateral_tilt"
    ] = {
        "left_tilt_threshold_deg": (
            neck_left
        ),

        "right_tilt_threshold_deg": (
            neck_right
        ),

        "unit": "deg",
    }

    # ========================================================
    # NECK FLEXION
    # ========================================================

    flexion_rule = feature_rules.get(
        "neck_flexion"
    )

    if not isinstance(
        flexion_rule,
        Mapping,
    ):

        raise ValueError(
            "Missing assessment rule for neck_flexion"
        )

    if (
        flexion_rule.get(
            "unit"
        )
        !=
        "deg"
    ):

        raise ValueError(
            "Invalid rule unit for neck_flexion"
        )

    flexion_threshold = _required_threshold(
        flexion_rule,
        "flexion_threshold_deg",
        "neck_flexion",
    )

    extension_threshold = _required_threshold(
        flexion_rule,
        "extension_threshold_deg",
        "neck_flexion",
    )

    if extension_threshold >= flexion_threshold:

        raise ValueError(
            "neck_flexion directional thresholds "
            "must satisfy extension < flexion"
        )

    normalized[
        "features"
    ][
        "neck_flexion"
    ] = {
        "flexion_threshold_deg": (
            flexion_threshold
        ),

        "extension_threshold_deg": (
            extension_threshold
        ),

        "unit": "deg",
    }

    return normalized


# ============================================================
# CONTEXT VALIDATION
# ============================================================

def _context_allows_assessment(
    detection_result: Mapping[str, Any],
) -> tuple[
    bool,
    str,
    dict[str, Any],
]:

    context = detection_result.get(
        "context"
    )

    if not isinstance(
        context,
        Mapping,
    ):

        return (
            False,

            "CONTEXT_MISSING",

            {
                "state": None,

                "allow_posture_evaluation": False,

                "reason": (
                    "CONTEXT_MISSING"
                ),
            },
        )

    state = context.get(
        "state"
    )

    allow = (
        context.get(
            "allow_posture_evaluation"
        )
        is True
    )

    normalized_context = {
        "state": state,

        "allow_posture_evaluation": (
            allow
        ),

        "reason": context.get(
            "reason"
        ),

        "stable_seconds": context.get(
            "stable_seconds"
        ),
    }

    if state != CONTEXT_VALID:

        return (
            False,

            (
                "CONTEXT_NOT_VALID:"
                f"{state}"
            ),

            normalized_context,
        )

    if not allow:

        return (
            False,

            "POSTURE_EVALUATION_NOT_ALLOWED",

            normalized_context,
        )

    return (
        True,
        "OK",
        normalized_context,
    )


# ============================================================
# FEATURE EXTRACTION
#
# Validation order:
#
# 1. features exists
# 2. feature exists
# 3. valid == True
# 4. unit is correct
# 5. value is finite
#
# DetectionPipeline invalid reason is preserved.
# ============================================================

def _extract_feature(
    detection_result: Mapping[str, Any],
    feature_name: str,
) -> tuple[
    bool,
    float | None,
    str,
    str | None,
]:

    features = detection_result.get(
        "features"
    )

    if not isinstance(
        features,
        Mapping,
    ):

        return (
            False,
            None,
            "FEATURES_MISSING",
            None,
        )

    feature = features.get(
        feature_name
    )

    if not isinstance(
        feature,
        Mapping,
    ):

        return (
            False,
            None,
            "FEATURE_MISSING",
            None,
        )

    # --------------------------------------------------------
    # Preserve DetectionPipeline invalid reason first.
    # --------------------------------------------------------

    if (
        feature.get(
            "valid"
        )
        is not True
    ):

        return (
            False,

            None,

            (
                feature.get(
                    "reason"
                )
                or
                "FEATURE_INVALID"
            ),

            feature.get(
                "unit"
            ),
        )

    expected_unit = (
        EXPECTED_UNITS[
            feature_name
        ]
    )

    actual_unit = feature.get(
        "unit"
    )

    if actual_unit != expected_unit:

        return (
            False,
            None,
            "INVALID_UNIT",
            actual_unit,
        )

    value = _finite_number(
        feature.get(
            "value"
        )
    )

    if value is None:

        return (
            False,
            None,
            "INVALID_VALUE",
            actual_unit,
        )

    return (
        True,
        value,
        "OK",
        actual_unit,
    )


# ============================================================
# CLASSIFICATION
#
# IMPORTANT:
#
# Strict comparisons are intentional.
#
# Exact boundary remains neutral.
# ============================================================

def _assess_shoulder_tilt(
    value: float,
    rule: Mapping[str, Any],
) -> str:

    left_threshold = (
        rule[
            "left_high_threshold_deg"
        ]
    )

    right_threshold = (
        rule[
            "right_high_threshold_deg"
        ]
    )

    if value < left_threshold:

        return (
            LEFT_SHOULDER_HIGH
        )

    if value > right_threshold:

        return (
            RIGHT_SHOULDER_HIGH
        )

    return (
        SHOULDER_NEAR_LEVEL
    )


def _assess_neck_lateral(
    value: float,
    rule: Mapping[str, Any],
) -> str:

    left_threshold = (
        rule[
            "left_tilt_threshold_deg"
        ]
    )

    right_threshold = (
        rule[
            "right_tilt_threshold_deg"
        ]
    )

    if value > left_threshold:

        return (
            NECK_TILT_LEFT
        )

    if value < right_threshold:

        return (
            NECK_TILT_RIGHT
        )

    return (
        NECK_LATERAL_NEUTRAL
    )


def _assess_neck_flexion(
    value: float,
    rule: Mapping[str, Any],
) -> str:

    flexion_threshold = (
        rule[
            "flexion_threshold_deg"
        ]
    )

    extension_threshold = (
        rule[
            "extension_threshold_deg"
        ]
    )

    if value > flexion_threshold:

        return (
            NECK_FLEXION
        )

    if value < extension_threshold:

        return (
            NECK_EXTENSION
        )

    return (
        NECK_FLEXION_NEUTRAL
    )


FEATURE_ASSESSORS = {
    "shoulder_tilt": (
        _assess_shoulder_tilt
    ),

    "neck_lateral_tilt": (
        _assess_neck_lateral
    ),

    "neck_flexion": (
        _assess_neck_flexion
    ),
}


# ============================================================
# RULE METADATA
# ============================================================

def _rule_metadata(
    feature_name: str,
    rule: Mapping[str, Any],
) -> dict[str, Any]:

    if feature_name == "shoulder_tilt":

        return {
            "left_high_threshold_deg": (
                rule[
                    "left_high_threshold_deg"
                ]
            ),

            "right_high_threshold_deg": (
                rule[
                    "right_high_threshold_deg"
                ]
            ),
        }

    if (
        feature_name
        ==
        "neck_lateral_tilt"
    ):

        return {
            "left_tilt_threshold_deg": (
                rule[
                    "left_tilt_threshold_deg"
                ]
            ),

            "right_tilt_threshold_deg": (
                rule[
                    "right_tilt_threshold_deg"
                ]
            ),
        }

    if feature_name == "neck_flexion":

        return {
            "flexion_threshold_deg": (
                rule[
                    "flexion_threshold_deg"
                ]
            ),

            "extension_threshold_deg": (
                rule[
                    "extension_threshold_deg"
                ]
            ),
        }

    return {}


# ============================================================
# NOT EVALUATED RESULT
# ============================================================

def _not_evaluated_feature(
    *,
    feature_name: str,
    reason: str,
    value: float | None = None,
    unit: str | None = None,
    rule: Mapping[str, Any] | None = None,
) -> dict[str, Any]:

    return {
        "feature": (
            feature_name
        ),

        "status": (
            STATUS_NOT_EVALUATED
        ),

        "reason": (
            reason
        ),

        "current": (
            value
        ),

        "absolute_current": (
            abs(value)
            if value is not None
            else None
        ),

        "thresholds": (
            _rule_metadata(
                feature_name,
                rule,
            )
            if rule is not None
            else {}
        ),

        "unit": (
            unit
        ),

        "evaluated": False,

        "is_posture_factor": False,
    }


# ============================================================
# INTERACTION BUILDER
# ============================================================

def _build_interaction_metadata(
    feature_results: Mapping[str, Any],
) -> dict[str, Any]:

    return (
        build_assessment_interactions(
            feature_results
        )
    )


# ============================================================
# MAIN
# ============================================================

def assess_current_posture(
    detection_result: Mapping[str, Any],
    rules: Mapping[str, Any] | None = None,
) -> dict[str, Any]:

    # ========================================================
    # INPUT TYPE
    # ========================================================

    if not isinstance(
        detection_result,
        Mapping,
    ):

        raise ValueError(
            "detection_result must be a mapping"
        )

    # ========================================================
    # DETECTION CONTRACT
    # ========================================================

    detection_contract = (
        detection_result.get(
            "contract_version"
        )
    )

    if (
        detection_contract
        !=
        EXPECTED_DETECTION_CONTRACT_VERSION
    ):

        raise ValueError(
            "Unsupported DetectionPipeline "
            "contract_version: "
            f"{detection_contract!r}"
        )

    # ========================================================
    # RULES
    # ========================================================

    if rules is None:

        rules = (
            DEFAULT_RULES
        )

    normalized_rules = (
        _validate_rules(
            rules
        )
    )

    # ========================================================
    # CONTEXT
    # ========================================================

    (
        context_ok,
        context_reason,
        context,
    ) = (
        _context_allows_assessment(
            detection_result
        )
    )

    timestamp = _finite_number(
        detection_result.get(
            "timestamp"
        )
    )

    # ========================================================
    # INVALID CONTEXT
    # ========================================================

    if not context_ok:

        feature_results = {}

        for feature_name in (
            REQUIRED_FEATURES
        ):

            rule = (
                normalized_rules[
                    "features"
                ][
                    feature_name
                ]
            )

            feature_results[
                feature_name
            ] = (
                _not_evaluated_feature(
                    feature_name=(
                        feature_name
                    ),

                    reason=(
                        context_reason
                    ),

                    value=None,

                    unit=(
                        rule[
                            "unit"
                        ]
                    ),

                    rule=rule,
                )
            )

        interaction_metadata = (
            _build_interaction_metadata(
                feature_results
            )
        )

        return {
            "contract_version": (
                ASSESSMENT_CONTRACT_VERSION
            ),

            "source_contract_version": (
                detection_contract
            ),

            "timestamp": (
                timestamp
            ),

            "status": (
                ASSESSMENT_NOT_EVALUATED
            ),

            "evaluable": False,

            "reason": (
                context_reason
            ),

            "context": (
                context
            ),

            "rules_version": (
                normalized_rules[
                    "version"
                ]
            ),

            "semantics": (
                deepcopy(
                    FEATURE_SEMANTICS
                )
            ),

            "features": (
                feature_results
            ),

            "evaluated_feature_count": 0,

            "not_evaluated_feature_count": (
                len(
                    REQUIRED_FEATURES
                )
            ),

            "factor_count": 0,

            "factors": [],

            # ----------------------------------------------
            # Descriptive interpretation metadata only.
            # ----------------------------------------------

            "interactions": (
                interaction_metadata
            ),

            # ----------------------------------------------
            # Reserved downstream layers.
            # ----------------------------------------------

            "risk": None,

            "alert": None,
        }

    # ========================================================
    # FEATURES
    # ========================================================

    results = {}

    factors = []

    evaluated_count = 0

    not_evaluated_count = 0

    for feature_name in (
        REQUIRED_FEATURES
    ):

        rule = (
            normalized_rules[
                "features"
            ][
                feature_name
            ]
        )

        (
            feature_ok,
            value,
            feature_reason,
            unit,
        ) = _extract_feature(
            detection_result,
            feature_name,
        )

        # ====================================================
        # FEATURE NOT EVALUATED
        # ====================================================

        if not feature_ok:

            results[
                feature_name
            ] = (
                _not_evaluated_feature(
                    feature_name=(
                        feature_name
                    ),

                    reason=(
                        feature_reason
                    ),

                    value=(
                        value
                    ),

                    unit=(
                        unit
                        or
                        rule[
                            "unit"
                        ]
                    ),

                    rule=(
                        rule
                    ),
                )
            )

            not_evaluated_count += 1

            continue

        # ====================================================
        # CLASSIFICATION
        # ====================================================

        assessor = (
            FEATURE_ASSESSORS[
                feature_name
            ]
        )

        posture_status = (
            assessor(
                value,
                rule,
            )
        )

        evaluated_count += 1

        neutral_states = {
            SHOULDER_NEAR_LEVEL,
            NECK_LATERAL_NEUTRAL,
            NECK_FLEXION_NEUTRAL,
        }

        is_factor = (
            posture_status
            not in
            neutral_states
        )

        feature_result = {
            "feature": (
                feature_name
            ),

            "status": (
                posture_status
            ),

            "reason": (
                "RULE_MATCH"
            ),

            "current": (
                value
            ),

            "absolute_current": (
                abs(
                    value
                )
            ),

            "thresholds": (
                _rule_metadata(
                    feature_name,
                    rule,
                )
            ),

            "unit": (
                unit
            ),

            "evaluated": True,

            "is_posture_factor": (
                is_factor
            ),
        }

        results[
            feature_name
        ] = (
            feature_result
        )

        if is_factor:

            factors.append({
                "feature": (
                    feature_name
                ),

                "factor": (
                    posture_status
                ),

                "value": (
                    value
                ),

                "unit": (
                    unit
                ),
            })

    # ========================================================
    # OVERALL STATUS
    # ========================================================

    if (
        evaluated_count
        ==
        len(
            REQUIRED_FEATURES
        )
    ):

        overall_status = (
            ASSESSMENT_COMPLETE
        )

        overall_reason = (
            "ALL_REQUIRED_FEATURES_EVALUATED"
        )

    elif evaluated_count > 0:

        overall_status = (
            ASSESSMENT_PARTIAL
        )

        overall_reason = (
            "SOME_FEATURES_NOT_EVALUATED"
        )

    else:

        overall_status = (
            ASSESSMENT_NOT_EVALUATED
        )

        overall_reason = (
            "NO_FEATURES_EVALUATED"
        )

    # ========================================================
    # INTERACTION METADATA
    #
    # IMPORTANT:
    #
    # This happens AFTER classification.
    #
    # It cannot change:
    #
    # - status
    # - factors
    # - thresholds
    # - risk
    # - alert
    # ========================================================

    interaction_metadata = (
        _build_interaction_metadata(
            results
        )
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "contract_version": (
            ASSESSMENT_CONTRACT_VERSION
        ),

        "source_contract_version": (
            detection_contract
        ),

        "timestamp": (
            timestamp
        ),

        "status": (
            overall_status
        ),

        "evaluable": (
            evaluated_count > 0
        ),

        "reason": (
            overall_reason
        ),

        "context": (
            context
        ),

        "rules_version": (
            normalized_rules[
                "version"
            ]
        ),

        # ----------------------------------------------------
        # Explicit feature semantics.
        # ----------------------------------------------------

        "semantics": (
            deepcopy(
                FEATURE_SEMANTICS
            )
        ),

        # ----------------------------------------------------
        # Original feature classifications.
        # ----------------------------------------------------

        "features": (
            results
        ),

        "evaluated_feature_count": (
            evaluated_count
        ),

        "not_evaluated_feature_count": (
            not_evaluated_count
        ),

        "factor_count": (
            len(
                factors
            )
        ),

        "factors": (
            factors
        ),

        # ----------------------------------------------------
        # Interpretation metadata only.
        # ----------------------------------------------------

        "interactions": (
            interaction_metadata
        ),

        # ----------------------------------------------------
        # Reserved future layers.
        # ----------------------------------------------------

        "risk": None,

        "alert": None,
    }


# ============================================================
# PUBLIC RULE COPY
# ============================================================

def get_default_assessment_rules() -> dict[str, Any]:

    return deepcopy(
        DEFAULT_RULES
    )


# ============================================================
# PUBLIC SEMANTICS COPY
# ============================================================

def get_assessment_feature_semantics() -> dict[str, Any]:

    return deepcopy(
        FEATURE_SEMANTICS
    )