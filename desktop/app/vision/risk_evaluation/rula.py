"""Camera-supported subset of the RULA neck assessment.

PostGuard currently measures neck flexion and lateral side-bending. Neck
twist and the other body groups are not inferred, so this module deliberately
does not calculate a Full RULA score or action level.
"""

from __future__ import annotations

import math
from collections.abc import Mapping


RULA_CONTRACT_VERSION = "1.1-camera-neck"


class RulaInputError(ValueError):
    """Raised when a camera-supported RULA observation is invalid."""


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RulaInputError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise RulaInputError(f"{name} must be a finite number")
    return value


def neck_score(flexion_deg, *, side_bent=False):
    """Return the observable RULA neck score, excluding neck twist."""
    angle = _number(flexion_deg, "neck_flexion_deg")
    if type(side_bent) is not bool:
        raise RulaInputError("side_bent must be boolean")
    if angle < 0:
        score = 4
    elif angle <= 10:
        score = 1
    elif angle <= 20:
        score = 2
    else:
        score = 3
    return min(5, score + int(side_bent))


def camera_rula_partial(assessment_result: Mapping, temporal_result: Mapping):
    """Map only camera-observable evidence to the RULA neck criteria."""
    if not isinstance(assessment_result, Mapping):
        raise RulaInputError("assessment_result must be a mapping")
    if not isinstance(temporal_result, Mapping):
        raise RulaInputError("temporal_result must be a mapping")

    assessment_features = assessment_result.get("features", {})
    temporal_features = temporal_result.get("features", {})
    neck_flexion = assessment_features.get("neck_flexion", {})
    neck_lateral = assessment_features.get("neck_lateral_tilt", {})
    duration_rows = [
        row.get("continuous_seconds")
        for row in temporal_features.values()
        if isinstance(row, Mapping) and row.get("active") is True
    ] if isinstance(temporal_features, Mapping) else []
    duration_rows = [
        float(value) for value in duration_rows
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and value >= 0
    ]

    flexion = neck_flexion.get("current") if isinstance(neck_flexion, Mapping) else None
    lateral_evaluated = (
        isinstance(neck_lateral, Mapping)
        and neck_lateral.get("evaluated") is True
    )
    flexion_evaluated = (
        isinstance(neck_flexion, Mapping)
        and neck_flexion.get("evaluated") is True
        and isinstance(flexion, (int, float))
        and not isinstance(flexion, bool)
        and math.isfinite(flexion)
    )
    side_bent = (
        lateral_evaluated and neck_lateral.get("is_posture_factor") is True
    )
    observable_score = (
        neck_score(float(flexion), side_bent=side_bent)
        if flexion_evaluated and lateral_evaluated
        else None
    )
    static_seconds = max(duration_rows, default=0.0)

    return {
        "contract_version": RULA_CONTRACT_VERSION,
        "status": "PARTIAL" if observable_score is not None else "NOT_EVALUATED",
        "source": "CAMERA_DERIVED",
        "body_region": "NECK",
        "neck_score_lower_bound": observable_score,
        "neck_flexion_deg": float(flexion) if flexion_evaluated else None,
        "neck_side_bent": side_bent if lateral_evaluated else None,
        "static_over_60_seconds": static_seconds > 60,
        "static_seconds": static_seconds,
        "missing": ["neck_twist"],
        "full_rula_score": None,
        "action_level": None,
        "limitations": [
            "Neck twist is not measured by the current Detection Contract.",
            "This is a partial neck score, not a Full RULA score.",
        ],
    }
