from __future__ import annotations

import math
from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

POSTURE_SCORE_CONTRACT_VERSION = "1.0"

EXPECTED_ASSESSMENT_CONTRACT_VERSION = "1.1"
EXPECTED_TEMPORAL_CONTRACT_VERSION = "1.0"


# ============================================================
# STATUS
# ============================================================

SCORE_STATUS_COMPLETE = "COMPLETE"
SCORE_STATUS_PARTIAL = "PARTIAL"
SCORE_STATUS_NOT_EVALUATED = "NOT_EVALUATED"


# ============================================================
# REQUIRED FEATURES
# ============================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
)


# ============================================================
# ASSESSMENT STATES
# ============================================================

SHOULDER_NEUTRAL = "NEAR_LEVEL"
LEFT_SHOULDER_HIGH = "LEFT_SHOULDER_HIGH"
RIGHT_SHOULDER_HIGH = "RIGHT_SHOULDER_HIGH"

NECK_LATERAL_NEUTRAL = "NEUTRAL"
NECK_TILT_LEFT = "TILT_LEFT"
NECK_TILT_RIGHT = "TILT_RIGHT"

NECK_FLEXION_NEUTRAL = "NEUTRAL"
NECK_FLEXION = "FLEXION"
NECK_EXTENSION = "EXTENSION"


# ============================================================
# SCORE POLICY
#
# IMPORTANT
#
# This is PostGuard Modified RULA for the validated
# front-view feature set.
#
# It is NOT Full RULA.
#
# Current available components:
#
# Neck base             1-4
# Neck lateral bend     0-1
# Shoulder asymmetry    0-1
# Sustained posture     0-1
#
# Maximum = 7
# ============================================================

MIN_MODIFIED_RULA_SCORE = 1
MAX_MODIFIED_RULA_SCORE = 7

SUSTAINED_POSTURE_SECONDS = 60.0


# ============================================================
# ERROR
# ============================================================

class ModifiedRULAError(ValueError):
    pass


# ============================================================
# HELPERS
# ============================================================

def _as_mapping(
    value: Any,
) -> Mapping[str, Any] | None:

    if isinstance(
        value,
        Mapping,
    ):
        return value

    return None


def _finite_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

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


def _finite_non_negative_number(
    value: Any,
) -> float | None:

    number = _finite_number(
        value
    )

    if number is None:
        return None

    if number < 0.0:
        return None

    return number


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def _validate_assessment_contract(
    assessment_result: Mapping[str, Any],
) -> None:

    if not isinstance(
        assessment_result,
        Mapping,
    ):
        raise ModifiedRULAError(
            "assessment_result must be a mapping"
        )

    contract_version = (
        assessment_result.get(
            "contract_version"
        )
    )

    if (
        contract_version
        != EXPECTED_ASSESSMENT_CONTRACT_VERSION
    ):
        raise ModifiedRULAError(
            "Unsupported Assessment contract_version: "
            f"{contract_version!r}"
        )


def _validate_temporal_contract(
    temporal_result: Mapping[str, Any],
) -> None:

    if not isinstance(
        temporal_result,
        Mapping,
    ):
        raise ModifiedRULAError(
            "temporal_result must be a mapping"
        )

    contract_version = (
        temporal_result.get(
            "contract_version"
        )
    )

    if (
        contract_version
        != EXPECTED_TEMPORAL_CONTRACT_VERSION
    ):
        raise ModifiedRULAError(
            "Unsupported Temporal contract_version: "
            f"{contract_version!r}"
        )


# ============================================================
# FEATURE READER
# ============================================================

def _read_assessment_feature(
    assessment_result: Mapping[str, Any],
    feature_name: str,
) -> dict[str, Any]:

    features = _as_mapping(
        assessment_result.get(
            "features"
        )
    )

    if features is None:
        return {
            "available": False,
            "reason": "ASSESSMENT_FEATURES_MISSING",
            "status": None,
            "current": None,
            "is_posture_factor": False,
        }

    feature = _as_mapping(
        features.get(
            feature_name
        )
    )

    if feature is None:
        return {
            "available": False,
            "reason": "ASSESSMENT_FEATURE_MISSING",
            "status": None,
            "current": None,
            "is_posture_factor": False,
        }

    if (
        feature.get(
            "evaluated"
        )
        is not True
    ):
        return {
            "available": False,
            "reason": (
                feature.get(
                    "reason"
                )
                or
                "ASSESSMENT_FEATURE_NOT_EVALUATED"
            ),
            "status": None,
            "current": None,
            "is_posture_factor": False,
        }

    status = feature.get(
        "status"
    )

    current = _finite_number(
        feature.get(
            "current"
        )
    )

    if (
        not isinstance(
            status,
            str,
        )
        or
        not status
    ):
        return {
            "available": False,
            "reason": "ASSESSMENT_STATUS_MISSING",
            "status": None,
            "current": current,
            "is_posture_factor": False,
        }

    if current is None:
        return {
            "available": False,
            "reason": "ASSESSMENT_CURRENT_VALUE_INVALID",
            "status": status,
            "current": None,
            "is_posture_factor": False,
        }

    return {
        "available": True,
        "reason": "OK",
        "status": status,
        "current": current,
        "is_posture_factor": (
            feature.get(
                "is_posture_factor"
            )
            is True
        ),
    }


def _read_temporal_feature(
    temporal_result: Mapping[str, Any],
    feature_name: str,
) -> dict[str, Any]:

    features = _as_mapping(
        temporal_result.get(
            "features"
        )
    )

    if features is None:
        return {
            "available": False,
            "reason": "TEMPORAL_FEATURES_MISSING",
            "factor": None,
            "continuous_seconds": None,
        }

    feature = _as_mapping(
        features.get(
            feature_name
        )
    )

    if feature is None:
        return {
            "available": False,
            "reason": "TEMPORAL_FEATURE_MISSING",
            "factor": None,
            "continuous_seconds": None,
        }

    if (
        feature.get(
            "evaluable"
        )
        is not True
    ):
        return {
            "available": False,
            "reason": (
                feature.get(
                    "reason"
                )
                or
                "TEMPORAL_FEATURE_NOT_EVALUATED"
            ),
            "factor": None,
            "continuous_seconds": None,
        }

    duration = (
        _finite_non_negative_number(
            feature.get(
                "continuous_seconds"
            )
        )
    )

    if duration is None:
        return {
            "available": False,
            "reason": "TEMPORAL_DURATION_INVALID",
            "factor": feature.get(
                "factor"
            ),
            "continuous_seconds": None,
        }

    factor = feature.get(
        "factor"
    )

    if factor is not None:
        factor = str(
            factor
        )

    return {
        "available": True,
        "reason": "OK",
        "factor": factor,
        "continuous_seconds": duration,
    }


# ============================================================
# NECK BASE SCORE
#
# Front-view PostGuard Modified RULA:
#
# Neutral / <= 10 deg flexion    = 1
# >10 to <=20 flexion            = 2
# >20 flexion                    = 3
# Extension                      = 4
#
# Extension is determined by the validated Assessment state,
# not by inventing another threshold here.
# ============================================================

def _neck_base_score(
    neck_feature: Mapping[str, Any],
) -> dict[str, Any]:

    status = neck_feature[
        "status"
    ]

    angle = float(
        neck_feature[
            "current"
        ]
    )

    if status == NECK_EXTENSION:

        return {
            "score": 4,
            "reason": "NECK_EXTENSION",
            "angle_deg": angle,
        }

    if status == NECK_FLEXION:

        if angle <= 20.0:

            return {
                "score": 2,
                "reason": (
                    "NECK_FLEXION_GT_10_TO_20_DEG"
                ),
                "angle_deg": angle,
            }

        return {
            "score": 3,
            "reason": "NECK_FLEXION_GT_20_DEG",
            "angle_deg": angle,
        }

    if status == NECK_FLEXION_NEUTRAL:

        return {
            "score": 1,
            "reason": (
                "NECK_NEUTRAL_OR_WITHIN_10_DEG"
            ),
            "angle_deg": angle,
        }

    raise ModifiedRULAError(
        "Unsupported neck_flexion status: "
        f"{status!r}"
    )


# ============================================================
# NECK LATERAL SCORE
# ============================================================

def _neck_lateral_score(
    feature: Mapping[str, Any],
) -> dict[str, Any]:

    status = feature[
        "status"
    ]

    if status in (
        NECK_TILT_LEFT,
        NECK_TILT_RIGHT,
    ):
        return {
            "score": 1,
            "reason": "NECK_SIDE_BENDING_PRESENT",
            "factor": status,
        }

    if status == NECK_LATERAL_NEUTRAL:

        return {
            "score": 0,
            "reason": "NO_NECK_SIDE_BENDING",
            "factor": None,
        }

    raise ModifiedRULAError(
        "Unsupported neck_lateral_tilt status: "
        f"{status!r}"
    )


# ============================================================
# SHOULDER ASYMMETRY SCORE
#
# This is a PostGuard-specific front-view component.
#
# It is NOT claimed to be equivalent to Full RULA shoulder/
# upper-arm scoring.
# ============================================================

def _shoulder_asymmetry_score(
    feature: Mapping[str, Any],
) -> dict[str, Any]:

    status = feature[
        "status"
    ]

    if status in (
        LEFT_SHOULDER_HIGH,
        RIGHT_SHOULDER_HIGH,
    ):
        return {
            "score": 1,
            "reason": "SHOULDER_ASYMMETRY_PRESENT",
            "factor": status,
        }

    if status == SHOULDER_NEUTRAL:

        return {
            "score": 0,
            "reason": "SHOULDERS_NEAR_LEVEL",
            "factor": None,
        }

    raise ModifiedRULAError(
        "Unsupported shoulder_tilt status: "
        f"{status!r}"
    )


# ============================================================
# SUSTAINED POSTURE SCORE
#
# Score only ONCE even if multiple features are sustained.
#
# Assessment factor must match Temporal factor.
# ============================================================

def _sustained_score(
    assessment_features: Mapping[
        str,
        Mapping[str, Any],
    ],
    temporal_features: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> dict[str, Any]:

    sustained_features = []

    for feature_name in REQUIRED_FEATURES:

        assessment = (
            assessment_features[
                feature_name
            ]
        )

        temporal = (
            temporal_features[
                feature_name
            ]
        )

        assessment_factor = (
            assessment[
                "status"
            ]
            if assessment[
                "is_posture_factor"
            ]
            else None
        )

        temporal_factor = (
            temporal[
                "factor"
            ]
        )

        # ----------------------------------------------------
        # Assessment / Temporal must describe the same factor.
        # ----------------------------------------------------

        if (
            assessment_factor
            != temporal_factor
        ):
            raise ModifiedRULAError(
                "Assessment/Temporal factor mismatch for "
                f"{feature_name}: "
                f"{assessment_factor!r} != "
                f"{temporal_factor!r}"
            )

        if assessment_factor is None:
            continue

        duration = float(
            temporal[
                "continuous_seconds"
            ]
        )

        if (
            duration
            >= SUSTAINED_POSTURE_SECONDS
        ):
            sustained_features.append({
                "feature": feature_name,
                "factor": assessment_factor,
                "continuous_seconds": duration,
            })

    return {
        "score": (
            1
            if sustained_features
            else 0
        ),

        "threshold_seconds": (
            SUSTAINED_POSTURE_SECONDS
        ),

        "sustained_features": (
            sustained_features
        ),

        "reason": (
            "SUSTAINED_POSTURE_PRESENT"
            if sustained_features
            else
            "NO_SUSTAINED_POSTURE"
        ),
    }


# ============================================================
# USER-FACING SCORE
#
# Modified RULA:
#
# 1 ->   0
# 2 ->  17
# 3 ->  33
# 4 ->  50
# 5 ->  67
# 6 ->  83
# 7 -> 100
#
# Formula:
#
# ((score - 1) / 6) * 100
#
# This 0-100 score is a PostGuard presentation score.
# It is NOT an original RULA score.
# ============================================================

def modified_rula_to_postguard_score(
    score: int,
) -> int:

    if (
        type(score) is not int
        or
        score < MIN_MODIFIED_RULA_SCORE
        or
        score > MAX_MODIFIED_RULA_SCORE
    ):
        raise ModifiedRULAError(
            "Modified RULA score must be "
            "an integer from 1 to 7"
        )

    normalized = (
        (
            score
            -
            MIN_MODIFIED_RULA_SCORE
        )
        /
        (
            MAX_MODIFIED_RULA_SCORE
            -
            MIN_MODIFIED_RULA_SCORE
        )
    )

    return int(
        round(
            normalized
            * 100.0
        )
    )


# ============================================================
# UNAVAILABLE OUTPUT
# ============================================================

def _unavailable_result(
    *,
    status: str,
    reason: str,
    missing_features: list[str],
) -> dict[str, Any]:

    return {
        "posture_score_contract_version": (
            POSTURE_SCORE_CONTRACT_VERSION
        ),

        "status": status,

        "reason": reason,

        "modified_rula_score": None,

        "postguard_risk_score": None,

        "score_range": {
            "modified_rula_min": 1,
            "modified_rula_max": 7,
            "postguard_min": 0,
            "postguard_max": 100,
        },

        "components": None,

        "missing_features": (
            list(
                missing_features
            )
        ),

        "method": {
            "name": (
                "POSTGUARD_MODIFIED_RULA_FRONT_VIEW"
            ),

            "version": "1.0",

            "is_full_rula": False,

            "uses_validated_runtime_features_only": True,

            "user_score_is_original_rula_score": False,
        },
    }


# ============================================================
# MAIN
# ============================================================

def calculate_modified_rula_score(
    assessment_result: Mapping[str, Any],
    temporal_result: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Calculate PostGuard Modified RULA v1.0.

    Input:
        Current Posture Assessment v1.1
        Temporal Tracking v1.0

    Output:
        modified_rula_score: 1-7
        postguard_risk_score: 0-100

    Important:
        This module does NOT decide Risk Event.
        This module does NOT send Alert.
    """

    _validate_assessment_contract(
        assessment_result
    )

    _validate_temporal_contract(
        temporal_result
    )

    # ========================================================
    # Read all required features
    # ========================================================

    assessment_features: (
        dict[str, dict[str, Any]]
    ) = {}

    temporal_features: (
        dict[str, dict[str, Any]]
    ) = {}

    missing_features: list[str] = []

    for feature_name in REQUIRED_FEATURES:

        assessment_feature = (
            _read_assessment_feature(
                assessment_result,
                feature_name,
            )
        )

        temporal_feature = (
            _read_temporal_feature(
                temporal_result,
                feature_name,
            )
        )

        assessment_features[
            feature_name
        ] = assessment_feature

        temporal_features[
            feature_name
        ] = temporal_feature

        if (
            assessment_feature[
                "available"
            ]
            is not True
            or
            temporal_feature[
                "available"
            ]
            is not True
        ):
            missing_features.append(
                feature_name
            )

    # ========================================================
    # Incomplete data
    #
    # Do not invent score when any required feature cannot
    # currently be evaluated.
    # ========================================================

    if missing_features:

        overall_assessment_status = (
            assessment_result.get(
                "status"
            )
        )

        if (
            overall_assessment_status
            ==
            "NOT_EVALUATED"
        ):
            score_status = (
                SCORE_STATUS_NOT_EVALUATED
            )

        else:
            score_status = (
                SCORE_STATUS_PARTIAL
            )

        return _unavailable_result(
            status=score_status,
            reason=(
                "REQUIRED_SCORE_FEATURES_UNAVAILABLE"
            ),
            missing_features=(
                missing_features
            ),
        )

    # ========================================================
    # COMPONENT 1: Neck base
    # ========================================================

    neck_base = (
        _neck_base_score(
            assessment_features[
                "neck_flexion"
            ]
        )
    )

    # ========================================================
    # COMPONENT 2: Neck side bending
    # ========================================================

    neck_lateral = (
        _neck_lateral_score(
            assessment_features[
                "neck_lateral_tilt"
            ]
        )
    )

    # ========================================================
    # COMPONENT 3: Shoulder asymmetry
    # ========================================================

    shoulder = (
        _shoulder_asymmetry_score(
            assessment_features[
                "shoulder_tilt"
            ]
        )
    )

    # ========================================================
    # COMPONENT 4: Sustained posture
    # ========================================================

    try:
        sustained = (
            _sustained_score(
                assessment_features,
                temporal_features,
            )
        )

    except ModifiedRULAError as exc:

        return _unavailable_result(
            status=(
                SCORE_STATUS_PARTIAL
            ),
            reason=str(
                exc
            ),
            missing_features=[],
        )

    # ========================================================
    # TOTAL
    # ========================================================

    total = (
        int(
            neck_base[
                "score"
            ]
        )
        +
        int(
            neck_lateral[
                "score"
            ]
        )
        +
        int(
            shoulder[
                "score"
            ]
        )
        +
        int(
            sustained[
                "score"
            ]
        )
    )

    total = max(
        MIN_MODIFIED_RULA_SCORE,
        min(
            MAX_MODIFIED_RULA_SCORE,
            total,
        ),
    )

    postguard_score = (
        modified_rula_to_postguard_score(
            total
        )
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    return {
        "posture_score_contract_version": (
            POSTURE_SCORE_CONTRACT_VERSION
        ),

        "status": (
            SCORE_STATUS_COMPLETE
        ),

        "reason": (
            "MODIFIED_RULA_SCORE_AVAILABLE"
        ),

        "modified_rula_score": (
            total
        ),

        "postguard_risk_score": (
            postguard_score
        ),

        "score_range": {
            "modified_rula_min": 1,
            "modified_rula_max": 7,

            "postguard_min": 0,
            "postguard_max": 100,
        },

        "components": {
            "neck_base": (
                neck_base
            ),

            "neck_side_bending": (
                neck_lateral
            ),

            "shoulder_asymmetry": (
                shoulder
            ),

            "sustained_posture": (
                sustained
            ),
        },

        "missing_features": [],

        "method": {
            "name": (
                "POSTGUARD_MODIFIED_RULA_FRONT_VIEW"
            ),

            "version": "1.0",

            "is_full_rula": False,

            "uses_validated_runtime_features_only": True,

            "user_score_is_original_rula_score": False,
        },
    }