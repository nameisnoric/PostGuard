from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Mapping

from .risk_level_mapper import (
    map_prototype_risk_level,
)


# ============================================================
# CONTRACT
# ============================================================

RISK_CONTRACT_VERSION = "1.2"

EXPECTED_ASSESSMENT_CONTRACT_VERSION = "1.1"
EXPECTED_TEMPORAL_CONTRACT_VERSION = "1.0"

STATIC_DURATION_THRESHOLD_SECONDS = 60.0


# ============================================================
# REQUIRED FEATURES
# ============================================================

REQUIRED_FEATURES = (
    "shoulder_tilt",
    "neck_lateral_tilt",
    "neck_flexion",
)


# ============================================================
# EVIDENCE GROUPS
#
# Keep the existing v1.1 group names.
# Do NOT rename LATERAL_ASYMMETRY because existing
# regression tests already define this contract.
# ============================================================

EVIDENCE_GROUP_FEATURES = {
    "LATERAL_ASYMMETRY": (
        "shoulder_tilt",
        "neck_lateral_tilt",
    ),

    "NECK_SAGITTAL": (
        "neck_flexion",
    ),
}


# ============================================================
# ERROR
# ============================================================

class RiskEvaluationError(
    ValueError
):
    pass


# ============================================================
# BASIC HELPERS
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


def _finite_non_negative_number(
    value: Any,
) -> float | None:

    if value is None:
        return None

    # bool is a subclass of int.
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        number
    ):
        return None

    if number < 0.0:
        return None

    return number


# ============================================================
# CONTRACT READERS
#
# Important:
#
# Older Risk tests use:
#
# assessment_contract_version
# temporal_contract_version
#
# Actual Assessment / Temporal currently use:
#
# contract_version
#
# Risk v1.2 accepts both input shapes so the original
# regression suite remains usable while the real pipeline
# can connect directly.
# ============================================================

def _assessment_contract_version(
    assessment_result: Mapping[str, Any],
) -> Any:

    if "contract_version" in assessment_result:

        return assessment_result.get(
            "contract_version"
        )

    return assessment_result.get(
        "assessment_contract_version"
    )


def _temporal_contract_version(
    temporal_result: Mapping[str, Any],
) -> Any:

    if "contract_version" in temporal_result:

        return temporal_result.get(
            "contract_version"
        )

    return temporal_result.get(
        "temporal_contract_version"
    )


# ============================================================
# ASSESSMENT FEATURE NORMALIZER
#
# Supports BOTH:
#
# Legacy Risk-test shape:
#
# {
#     "valid": True,
#     "status": "EVALUATED",
#     "factor": "FLEXION"
# }
#
# Real Assessment v1.1 shape:
#
# {
#     "evaluated": True,
#     "status": "FLEXION",
#     "is_posture_factor": True
# }
# ============================================================

def _normalize_assessment_feature(
    feature_name: str,
    raw_feature: Any,
) -> dict[str, Any]:

    feature = _as_mapping(
        raw_feature
    )

    if feature is None:

        return {
            "feature": feature_name,
            "available": False,
            "factor": None,
            "reason": "ASSESSMENT_FEATURE_MISSING",
        }

    # ========================================================
    # REAL ASSESSMENT CONTRACT
    # ========================================================

    if (
        "evaluated" in feature
        or
        "is_posture_factor" in feature
    ):

        if (
            feature.get(
                "evaluated"
            )
            is not True
        ):

            return {
                "feature": feature_name,
                "available": False,
                "factor": None,
                "reason": (
                    feature.get(
                        "reason"
                    )
                    or
                    "ASSESSMENT_NOT_EVALUATED"
                ),
            }

        status = feature.get(
            "status"
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
                "feature": feature_name,
                "available": False,
                "factor": None,
                "reason": "ASSESSMENT_STATUS_MISSING",
            }

        is_factor = (
            feature.get(
                "is_posture_factor"
            )
            is True
        )

        return {
            "feature": feature_name,
            "available": True,

            "factor": (
                str(status)
                if is_factor
                else None
            ),

            "reason": "OK",
        }

    # ========================================================
    # LEGACY RISK TEST CONTRACT
    # ========================================================

    if (
        feature.get(
            "valid"
        )
        is not True
    ):

        return {
            "feature": feature_name,
            "available": False,
            "factor": None,
            "reason": (
                feature.get(
                    "reason"
                )
                or
                "ASSESSMENT_NOT_EVALUATED"
            ),
        }

    factor = feature.get(
        "factor"
    )

    if factor is not None:

        factor = str(
            factor
        )

    return {
        "feature": feature_name,
        "available": True,
        "factor": factor,
        "reason": "OK",
    }


# ============================================================
# TEMPORAL FEATURE NORMALIZER
#
# Supports BOTH:
#
# Legacy:
#
# {
#     "state": "ACTIVE",
#     "factor": "FLEXION",
#     "continuous_seconds": 30.0
# }
#
# Real Temporal v1.0:
#
# {
#     "state": "ACTIVE",
#     "factor": "FLEXION",
#     "continuous_seconds": 30.0,
#     "evaluable": True,
#     "active": True
# }
# ============================================================

def _normalize_temporal_feature(
    feature_name: str,
    raw_feature: Any,
) -> dict[str, Any]:

    feature = _as_mapping(
        raw_feature
    )

    if feature is None:

        return {
            "feature": feature_name,
            "available": False,
            "factor": None,
            "continuous_seconds": None,
            "reason": "TEMPORAL_FEATURE_MISSING",
        }

    state = feature.get(
        "state"
    )

    # ========================================================
    # Explicit real-contract evaluability
    # ========================================================

    if (
        "evaluable" in feature
        and
        feature.get(
            "evaluable"
        )
        is not True
    ):

        return {
            "feature": feature_name,
            "available": False,
            "factor": None,
            "continuous_seconds": None,
            "reason": (
                feature.get(
                    "reason"
                )
                or
                "TEMPORAL_NOT_EVALUATED"
            ),
        }

    # ========================================================
    # Legacy NOT_EVALUATED
    # ========================================================

    if state == "NOT_EVALUATED":

        return {
            "feature": feature_name,
            "available": False,
            "factor": None,
            "continuous_seconds": None,
            "reason": (
                feature.get(
                    "reason"
                )
                or
                "TEMPORAL_NOT_EVALUATED"
            ),
        }

    factor = feature.get(
        "factor"
    )

    if factor is not None:

        factor = str(
            factor
        )

    duration = (
        _finite_non_negative_number(
            feature.get(
                "continuous_seconds"
            )
        )
    )

    if duration is None:

        return {
            "feature": feature_name,
            "available": False,
            "factor": factor,
            "continuous_seconds": None,
            "reason": "INVALID_TEMPORAL_DURATION",
        }

    return {
        "feature": feature_name,
        "available": True,
        "factor": factor,
        "continuous_seconds": duration,
        "reason": "OK",
    }


# ============================================================
# CONSISTENCY CHECK
#
# Duration can be used ONLY when:
#
# Assessment factor == Temporal factor
#
# Examples:
#
# FLEXION == FLEXION
#     READY
#
# FLEXION != EXTENSION
#     FACTOR_MISMATCH
#
# NEUTRAL(None) != FLEXION
#     FACTOR_MISMATCH
#
# NEUTRAL(None) == NEUTRAL(None)
#     READY
# ============================================================

def _evaluate_feature_consistency(
    *,
    feature_name: str,
    assessment_feature: dict[str, Any],
    temporal_feature: dict[str, Any],
) -> dict[str, Any]:

    # ========================================================
    # Assessment unavailable
    # ========================================================

    if (
        assessment_feature[
            "available"
        ]
        is not True
    ):

        return {
            "feature": feature_name,

            "factor": None,

            "continuous_seconds": None,

            "static_duration_met": False,

            "consistency": {
                "status": (
                    "ASSESSMENT_NOT_EVALUATED"
                ),

                "reason": (
                    assessment_feature[
                        "reason"
                    ]
                ),
            },
        }

    # ========================================================
    # Temporal unavailable
    # ========================================================

    if (
        temporal_feature[
            "available"
        ]
        is not True
    ):

        return {
            "feature": feature_name,

            "factor": (
                assessment_feature[
                    "factor"
                ]
            ),

            "continuous_seconds": None,

            "static_duration_met": False,

            "consistency": {
                "status": (
                    "TEMPORAL_UNAVAILABLE"
                ),

                "reason": (
                    temporal_feature[
                        "reason"
                    ]
                ),
            },
        }

    assessment_factor = (
        assessment_feature[
            "factor"
        ]
    )

    temporal_factor = (
        temporal_feature[
            "factor"
        ]
    )

    # ========================================================
    # Mismatch
    # ========================================================

    if (
        assessment_factor
        !=
        temporal_factor
    ):

        return {
            "feature": feature_name,

            "factor": (
                assessment_factor
            ),

            # Duration MUST NOT be used when factors mismatch.
            "continuous_seconds": None,

            "static_duration_met": False,

            "consistency": {
                "status": (
                    "FACTOR_MISMATCH"
                ),

                "reason": (
                    "ASSESSMENT_TEMPORAL_FACTOR_MISMATCH"
                ),

                "assessment_factor": (
                    assessment_factor
                ),

                "temporal_factor": (
                    temporal_factor
                ),
            },
        }

    # ========================================================
    # Ready
    # ========================================================

    duration = (
        temporal_feature[
            "continuous_seconds"
        ]
    )

    # Neutral duration is semantically zero.
    if assessment_factor is None:

        duration = 0.0

    static_duration_met = (
        assessment_factor is not None
        and
        duration
        >=
        STATIC_DURATION_THRESHOLD_SECONDS
    )

    return {
        "feature": feature_name,

        "factor": (
            assessment_factor
        ),

        "continuous_seconds": (
            duration
        ),

        "static_duration_met": (
            static_duration_met
        ),

        "consistency": {
            "status": "READY",
            "reason": "ASSESSMENT_TEMPORAL_CONSISTENT",
        },
    }


# ============================================================
# RULA-DERIVED EVIDENCE
#
# Important:
#
# These are limited evidence labels only.
# This module does NOT calculate Full RULA.
# ============================================================

def _build_rula_derived_evidence(
    feature_results: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> list[dict[str, Any]]:

    evidence = []

    # ========================================================
    # Neck lateral
    # ========================================================

    neck_lateral = (
        feature_results[
            "neck_lateral_tilt"
        ]
    )

    if (
        neck_lateral[
            "consistency"
        ][
            "status"
        ]
        ==
        "READY"
        and
        neck_lateral[
            "factor"
        ]
        in (
            "TILT_LEFT",
            "TILT_RIGHT",
        )
    ):

        evidence.append({
            "type": (
                "NECK_SIDE_BENDING"
            ),

            "feature": (
                "neck_lateral_tilt"
            ),

            "factor": (
                neck_lateral[
                    "factor"
                ]
            ),

            "source": (
                "RULA_DERIVED_LIMITED_EVIDENCE"
            ),
        })

    # ========================================================
    # Neck sagittal
    # ========================================================

    neck_flexion = (
        feature_results[
            "neck_flexion"
        ]
    )

    if (
        neck_flexion[
            "consistency"
        ][
            "status"
        ]
        ==
        "READY"
        and
        neck_flexion[
            "factor"
        ]
        in (
            "FLEXION",
            "EXTENSION",
        )
    ):

        evidence.append({
            "type": (
                "NECK_FLEXION_EXTENSION"
            ),

            "feature": (
                "neck_flexion"
            ),

            "factor": (
                neck_flexion[
                    "factor"
                ]
            ),

            "source": (
                "RULA_DERIVED_LIMITED_EVIDENCE"
            ),
        })

    return evidence


# ============================================================
# POSTGUARD-SPECIFIC EVIDENCE
# ============================================================

def _build_postguard_specific_evidence(
    feature_results: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> list[dict[str, Any]]:

    evidence = []

    shoulder = (
        feature_results[
            "shoulder_tilt"
        ]
    )

    if (
        shoulder[
            "consistency"
        ][
            "status"
        ]
        ==
        "READY"
        and
        shoulder[
            "factor"
        ]
        in (
            "LEFT_SHOULDER_HIGH",
            "RIGHT_SHOULDER_HIGH",
        )
    ):

        evidence.append({
            "type": (
                "SHOULDER_ASYMMETRY"
            ),

            "feature": (
                "shoulder_tilt"
            ),

            "factor": (
                shoulder[
                    "factor"
                ]
            ),

            "source": (
                "POSTGUARD_PROTOTYPE"
            ),

            "rula_equivalent": False,
        })

    return evidence


# ============================================================
# TEMPORAL EVIDENCE
# ============================================================

def _build_temporal_evidence(
    feature_results: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> list[dict[str, Any]]:

    evidence = []

    for feature_name in REQUIRED_FEATURES:

        result = (
            feature_results[
                feature_name
            ]
        )

        if (
            result[
                "consistency"
            ][
                "status"
            ]
            !=
            "READY"
        ):

            continue

        if (
            result[
                "factor"
            ]
            is None
        ):

            continue

        if (
            result[
                "static_duration_met"
            ]
            is not True
        ):

            continue

        evidence.append({
            "type": (
                "STATIC_DURATION"
            ),

            "feature": (
                feature_name
            ),

            "factor": (
                result[
                    "factor"
                ]
            ),

            "continuous_seconds": (
                result[
                    "continuous_seconds"
                ]
            ),

            "threshold_seconds": (
                STATIC_DURATION_THRESHOLD_SECONDS
            ),

            "comparison": ">=",

            "source": (
                "POSTGUARD_TEMPORAL_PROTOTYPE"
            ),
        })

    return evidence


# ============================================================
# EVIDENCE GROUPS
# ============================================================

def _build_evidence_groups(
    feature_results: Mapping[
        str,
        Mapping[str, Any],
    ],
) -> dict[str, Any]:

    groups = {}

    for (
        group_name,
        feature_names,
    ) in EVIDENCE_GROUP_FEATURES.items():

        active_features = []
        static_features = []

        for feature_name in feature_names:

            result = (
                feature_results[
                    feature_name
                ]
            )

            if (
                result[
                    "consistency"
                ][
                    "status"
                ]
                !=
                "READY"
            ):

                continue

            if (
                result[
                    "factor"
                ]
                is None
            ):

                continue

            active_features.append(
                feature_name
            )

            if (
                result[
                    "static_duration_met"
                ]
                is True
            ):

                static_features.append(
                    feature_name
                )

        groups[
            group_name
        ] = {
            "active": bool(
                active_features
            ),

            "active_features": (
                active_features
            ),

            # risk_level_mapper.py already consumes
            # this exact field.
            "static_duration_met": bool(
                static_features
            ),

            "static_features": (
                static_features
            ),
        }

    return groups


# ============================================================
# MAIN
# ============================================================

def evaluate_risk(
    assessment_result: Mapping[str, Any],
    temporal_result: Mapping[str, Any],
) -> dict[str, Any]:

    """
    PostGuard Risk Evaluation Contract v1.2.

    Responsibilities
    ----------------
    1. Validate Assessment / Temporal contracts.
    2. Check factor consistency.
    3. Preserve continuous duration only when consistent.
    4. Produce limited ergonomic evidence.
    5. Group related evidence.
    6. Map evidence into PostGuard prototype risk level.

    Does NOT
    --------
    - calculate Full RULA score,
    - claim a RULA Action Level,
    - create Risk Event,
    - decide Alert,
    - send Notification.
    """

    # ========================================================
    # INPUT TYPE
    # ========================================================

    if not isinstance(
        assessment_result,
        Mapping,
    ):

        raise RiskEvaluationError(
            "assessment_result must be a mapping"
        )

    if not isinstance(
        temporal_result,
        Mapping,
    ):

        raise RiskEvaluationError(
            "temporal_result must be a mapping"
        )

    # ========================================================
    # CONTRACT VERSIONS
    # ========================================================

    assessment_contract = (
        _assessment_contract_version(
            assessment_result
        )
    )

    temporal_contract = (
        _temporal_contract_version(
            temporal_result
        )
    )

    if (
        assessment_contract
        !=
        EXPECTED_ASSESSMENT_CONTRACT_VERSION
    ):

        raise RiskEvaluationError(
            "Unsupported Assessment "
            "contract_version: "
            f"{assessment_contract!r}"
        )

    if (
        temporal_contract
        !=
        EXPECTED_TEMPORAL_CONTRACT_VERSION
    ):

        raise RiskEvaluationError(
            "Unsupported Temporal "
            "contract_version: "
            f"{temporal_contract!r}"
        )

    # ========================================================
    # REAL TEMPORAL SOURCE CONTRACT CHECK
    #
    # Legacy tests do not have this field.
    # When present, it MUST agree with the Assessment version.
    # ========================================================

    source_assessment_contract = (
        temporal_result.get(
            "source_assessment_contract_version"
        )
    )

    temporal_source_mismatch = False

    if (
        source_assessment_contract
        is not None
        and
        source_assessment_contract
        !=
        EXPECTED_ASSESSMENT_CONTRACT_VERSION
    ):

        temporal_source_mismatch = True

    # ========================================================
    # FEATURES
    # ========================================================

    assessment_features = (
        _as_mapping(
            assessment_result.get(
                "features"
            )
        )
    )

    temporal_features = (
        _as_mapping(
            temporal_result.get(
                "features"
            )
        )
    )

    if assessment_features is None:

        assessment_features = {}

    if temporal_features is None:

        temporal_features = {}

    feature_results = {}

    assessment_available_count = 0
    ready_count = 0

    # ========================================================
    # FEATURE LOOP
    # ========================================================

    for feature_name in REQUIRED_FEATURES:

        assessment_feature = (
            _normalize_assessment_feature(
                feature_name,
                assessment_features.get(
                    feature_name
                ),
            )
        )

        temporal_feature = (
            _normalize_temporal_feature(
                feature_name,
                temporal_features.get(
                    feature_name
                ),
            )
        )

        if (
            assessment_feature[
                "available"
            ]
        ):

            assessment_available_count += 1

        result = (
            _evaluate_feature_consistency(
                feature_name=(
                    feature_name
                ),

                assessment_feature=(
                    assessment_feature
                ),

                temporal_feature=(
                    temporal_feature
                ),
            )
        )

        feature_results[
            feature_name
        ] = result

        if (
            result[
                "consistency"
            ][
                "status"
            ]
            ==
            "READY"
        ):

            ready_count += 1

    # ========================================================
    # OVERALL EVALUATION STATUS
    # ========================================================

    if temporal_source_mismatch:

        evaluation_status = (
            "PARTIAL"
        )

        evaluation_reason = (
            "TEMPORAL_SOURCE_ASSESSMENT_CONTRACT_MISMATCH"
        )

    elif assessment_available_count == 0:

        evaluation_status = (
            "NOT_EVALUATED"
        )

        evaluation_reason = (
            "NO_REQUIRED_ASSESSMENT_FEATURES_EVALUATED"
        )

    elif (
        ready_count
        ==
        len(
            REQUIRED_FEATURES
        )
    ):

        evaluation_status = (
            "EVALUATED"
        )

        evaluation_reason = (
            "ALL_REQUIRED_EVIDENCE_READY"
        )

    else:

        evaluation_status = (
            "PARTIAL"
        )

        evaluation_reason = (
            "REQUIRED_EVIDENCE_INCOMPLETE_OR_INCONSISTENT"
        )

    # ========================================================
    # EVIDENCE
    # ========================================================

    rula_derived = (
        _build_rula_derived_evidence(
            feature_results
        )
    )

    postguard_specific = (
        _build_postguard_specific_evidence(
            feature_results
        )
    )

    temporal_evidence = (
        _build_temporal_evidence(
            feature_results
        )
    )

    evidence = {
        "rula_derived": (
            rula_derived
        ),

        "postguard_specific": (
            postguard_specific
        ),

        "temporal": (
            temporal_evidence
        ),
    }

    # ========================================================
    # GROUP EVIDENCE
    # ========================================================

    evidence_groups = (
        _build_evidence_groups(
            feature_results
        )
    )

    # ========================================================
    # RISK LEVEL MAPPING
    #
    # Mapper itself refuses to map incomplete evaluation.
    # ========================================================

    risk_level_result = (
        map_prototype_risk_level(
            evaluation_status=(
                evaluation_status
            ),

            evidence_groups=(
                evidence_groups
            ),
        )
    )

    risk_level = (
        risk_level_result[
            "level"
        ]
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    return {
        "risk_contract_version": (
            RISK_CONTRACT_VERSION
        ),

        "source_assessment_contract_version": (
            assessment_contract
        ),

        "source_temporal_contract_version": (
            temporal_contract
        ),

        "status": (
            evaluation_status
        ),

        "reason": (
            evaluation_reason
        ),

        # ====================================================
        # Feature-level validated information
        # ====================================================

        "feature_results": (
            feature_results
        ),

        # ====================================================
        # Evidence layers
        # ====================================================

        "evidence": (
            evidence
        ),

        "evidence_groups": (
            evidence_groups
        ),

        # ====================================================
        # Related geometric features do NOT automatically
        # increase a numeric score independently.
        # ====================================================

        "interaction_policy": {
            "automatic_score_addition": False,

            "shoulder_neck_lateral_same_group": True,
        },

        # ====================================================
        # Full RULA is explicitly unsupported.
        # ====================================================

        "full_rula": {
            "supported": False,
            "score": None,
            "action_level": None,
        },

        # ====================================================
        # RISK LEVEL v1.2
        # ====================================================

        "risk_level_mapping_enabled": True,

        "risk_level_available": (
            risk_level_result[
                "available"
            ]
        ),

        "risk_level": (
            risk_level
        ),

        "risk_level_mapping": deepcopy(
            risk_level_result
        ),

        # ====================================================
        # No numeric score in v1.2.
        # ====================================================

        "risk_score": None,

        # ====================================================
        # Future layers remain intentionally disabled.
        # ====================================================

        "risk_event": None,

        "alert": None,

        # ====================================================
        # Policy documentation
        # ====================================================

        "policy": {
            "type": (
                "POSTGUARD_PROTOTYPE_ENGINEERING_POLICY"
            ),

            "static_duration_threshold_seconds": (
                STATIC_DURATION_THRESHOLD_SECONDS
            ),

            "static_duration_comparison": ">=",

            "full_rula_supported": False,

            "rula_action_level_claimed": False,

            "clinical_risk_level_claimed": False,
        },
    }