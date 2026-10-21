from __future__ import annotations

from typing import Any, Mapping


# ============================================================
# CONTRACT
# ============================================================

INTERACTION_CONTRACT_VERSION = "1.0"


# ============================================================
# INTERACTION TYPES
# ============================================================

INTERACTION_GEOMETRICALLY_COUPLED = (
    "GEOMETRICALLY_COUPLED"
)

INTERACTION_NOT_EVALUATED = (
    "NOT_EVALUATED"
)


# ============================================================
# INTERACTION IDS
# ============================================================

SHOULDER_NECK_LATERAL_INTERACTION_ID = (
    "shoulder_neck_lateral_geometric_coupling"
)


# ============================================================
# FEATURE NAMES
# ============================================================

FEATURE_SHOULDER_TILT = "shoulder_tilt"

FEATURE_NECK_LATERAL_TILT = (
    "neck_lateral_tilt"
)


# ============================================================
# SEMANTICS
# ============================================================

FEATURE_SEMANTICS = {
    FEATURE_SHOULDER_TILT: {
        "name": "Shoulder Tilt",
        "measurement_semantics": (
            "Angle of the shoulder line according to "
            "the DetectionPipeline image-space definition."
        ),
        "unit": "deg",
    },

    FEATURE_NECK_LATERAL_TILT: {
        "name": "Relative Neck Lateral Tilt",
        "measurement_semantics": (
            "Relative angle between the ear/head line "
            "and the shoulder line."
        ),
        "formula": (
            "ear_angle - shoulder_angle"
        ),
        "unit": "deg",
    },
}


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


def _feature_is_evaluated(
    feature: Mapping[str, Any] | None,
) -> bool:

    if feature is None:
        return False

    return (
        feature.get(
            "evaluated"
        )
        is True
    )


def _feature_is_factor(
    feature: Mapping[str, Any] | None,
) -> bool:

    if feature is None:
        return False

    return (
        feature.get(
            "evaluated"
        )
        is True
        and
        feature.get(
            "is_posture_factor"
        )
        is True
    )


def _feature_status(
    feature: Mapping[str, Any] | None,
) -> str | None:

    if feature is None:
        return None

    status = feature.get(
        "status"
    )

    if status is None:
        return None

    return str(
        status
    )


def _feature_value(
    feature: Mapping[str, Any] | None,
) -> float | int | None:

    if feature is None:
        return None

    value = feature.get(
        "current"
    )

    if isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return value

    return None


# ============================================================
# SHOULDER / RELATIVE NECK INTERACTION
# ============================================================

def _build_shoulder_neck_lateral_interaction(
    features: Mapping[str, Any],
) -> dict[str, Any]:

    shoulder = _as_mapping(
        features.get(
            FEATURE_SHOULDER_TILT
        )
    )

    neck = _as_mapping(
        features.get(
            FEATURE_NECK_LATERAL_TILT
        )
    )

    shoulder_evaluated = (
        _feature_is_evaluated(
            shoulder
        )
    )

    neck_evaluated = (
        _feature_is_evaluated(
            neck
        )
    )

    both_evaluated = (
        shoulder_evaluated
        and
        neck_evaluated
    )

    shoulder_factor = (
        _feature_is_factor(
            shoulder
        )
    )

    neck_factor = (
        _feature_is_factor(
            neck
        )
    )

    classification_overlap = (
        both_evaluated
        and
        shoulder_factor
        and
        neck_factor
    )

    if both_evaluated:

        state = (
            INTERACTION_GEOMETRICALLY_COUPLED
        )

        active = True

        reason = (
            "RELATIVE_NECK_METRIC_USES_"
            "SHOULDER_ANGLE_REFERENCE"
        )

    else:

        state = (
            INTERACTION_NOT_EVALUATED
        )

        active = False

        missing = []

        if not shoulder_evaluated:
            missing.append(
                FEATURE_SHOULDER_TILT
            )

        if not neck_evaluated:
            missing.append(
                FEATURE_NECK_LATERAL_TILT
            )

        reason = (
            "REQUIRED_FEATURE_NOT_EVALUATED:"
            +
            ",".join(
                missing
            )
        )

    return {
        "id": (
            SHOULDER_NECK_LATERAL_INTERACTION_ID
        ),

        "type": state,

        "active": active,

        "reason": reason,

        "features": [
            FEATURE_SHOULDER_TILT,
            FEATURE_NECK_LATERAL_TILT,
        ],

        # ----------------------------------------------------
        # Why this interaction exists
        # ----------------------------------------------------

        "relationship": {
            "kind": (
                "REFERENCE_DEPENDENCY"
            ),

            "description": (
                "neck_lateral_tilt is defined relative "
                "to the shoulder line, therefore "
                "shoulder_tilt and neck_lateral_tilt "
                "are geometrically coupled measurements."
            ),

            "relative_metric": (
                FEATURE_NECK_LATERAL_TILT
            ),

            "reference_feature": (
                FEATURE_SHOULDER_TILT
            ),

            "formula": (
                "neck_lateral_tilt = "
                "ear_angle - shoulder_angle"
            ),
        },

        # ----------------------------------------------------
        # Current classification snapshot
        #
        # Descriptive only.
        # ----------------------------------------------------

        "classification": {
            "shoulder_status": (
                _feature_status(
                    shoulder
                )
            ),

            "neck_lateral_status": (
                _feature_status(
                    neck
                )
            ),

            "shoulder_is_factor": (
                shoulder_factor
            ),

            "neck_lateral_is_factor": (
                neck_factor
            ),

            "classification_overlap": (
                classification_overlap
            ),
        },

        # ----------------------------------------------------
        # Measurement snapshot
        #
        # No new calculation.
        # Uses Assessment results only.
        # ----------------------------------------------------

        "measurement": {
            "shoulder_tilt": (
                _feature_value(
                    shoulder
                )
            ),

            "neck_lateral_tilt": (
                _feature_value(
                    neck
                )
            ),

            "unit": "deg",
        },

        # ----------------------------------------------------
        # Interpretation contract
        # ----------------------------------------------------

        "interpretation": {
            "classification_preserved": True,

            "measurement_invalidated": False,

            "measurement_error_implied": False,

            "physical_cause_inferred": False,

            "medical_meaning": False,

            "risk_meaning": False,

            "diagnostic_meaning": False,

            "note": (
                "The interaction records a known "
                "geometric relationship between "
                "measurements. It does not determine "
                "that either classification is wrong."
            ),
        },

        # ----------------------------------------------------
        # Hard boundaries
        #
        # Future code must not interpret this metadata
        # as permission to change these layers.
        # ----------------------------------------------------

        "effects": {
            "changes_classification": False,

            "suppresses_factor": False,

            "changes_threshold": False,

            "changes_measurement_change_gate": False,

            "changes_risk": False,

            "changes_alert": False,

            "changes_temporal_tracking": False,
        },
    }


# ============================================================
# PUBLIC CONTRACT BUILDER
# ============================================================

def build_assessment_interactions(
    feature_results: Mapping[str, Any],
) -> dict[str, Any]:

    """
    Build interpretation metadata for Current Posture Assessment.

    IMPORTANT
    ---------
    This function is descriptive only.

    It MUST NOT:

    - reclassify posture
    - suppress factors
    - modify thresholds
    - calculate risk
    - calculate alert state
    - perform temporal tracking
    - use Personal Baseline
    - use Measurement-Change Gate
    """

    if not isinstance(
        feature_results,
        Mapping,
    ):
        raise ValueError(
            "feature_results must be a mapping"
        )

    interaction = (
        _build_shoulder_neck_lateral_interaction(
            feature_results
        )
    )

    interactions = [
        interaction
    ]

    active_count = sum(
        1
        for item in interactions
        if item.get(
            "active"
        )
        is True
    )

    overlap_count = sum(
        1
        for item in interactions
        if (
            item.get(
                "classification",
                {},
            ).get(
                "classification_overlap"
            )
            is True
        )
    )

    return {
        "contract_version": (
            INTERACTION_CONTRACT_VERSION
        ),

        "interactions": (
            interactions
        ),

        "active_interaction_count": (
            active_count
        ),

        "classification_overlap_count": (
            overlap_count
        ),

        "semantics": {
            "features": (
                FEATURE_SEMANTICS
            ),

            "interaction_type": {
                (
                    INTERACTION_GEOMETRICALLY_COUPLED
                ): (
                    "Features have a known geometric "
                    "relationship in their measurement "
                    "definitions. This does not imply "
                    "measurement error or invalid posture "
                    "classification."
                )
            },
        },

        "risk": None,

        "alert": None,
    }
