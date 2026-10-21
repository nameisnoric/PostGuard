"""RULA-inspired risk score for PostGuard's front-camera measurements.

This adaptation uses neck flexion/extension, lateral neck bending, shoulder
asymmetry and sustained posture. It is a simple 1-7 risk scale for users and
must not be presented as an official Full RULA calculation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping


RULA_CONTRACT_VERSION = "2.0-front-camera-adapted"


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


def _risk_level(score):
    if score <= 2:
        return "LOW"
    if score <= 4:
        return "MODERATE"
    if score <= 6:
        return "HIGH"
    return "VERY_HIGH"


def evaluate_front_camera_risk(
    assessment_result: Mapping,
    temporal_result: Mapping,
):
    """Calculate the PostGuard RULA-adapted 1-7 front-camera score."""
    if not isinstance(assessment_result, Mapping):
        raise RulaInputError("assessment_result must be a mapping")
    if not isinstance(temporal_result, Mapping):
        raise RulaInputError("temporal_result must be a mapping")

    assessment_features = assessment_result.get("features", {})
    temporal_features = temporal_result.get("features", {})
    neck_flexion = assessment_features.get("neck_flexion", {})
    neck_lateral = assessment_features.get("neck_lateral_tilt", {})
    shoulder_tilt = assessment_features.get("shoulder_tilt", {})
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
    shoulder_evaluated = (
        isinstance(shoulder_tilt, Mapping)
        and shoulder_tilt.get("evaluated") is True
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
    shoulder_asymmetric = (
        shoulder_evaluated and shoulder_tilt.get("is_posture_factor") is True
    )
    static_seconds = max(duration_rows, default=0.0)
    sustained = static_seconds > 60
    neck_base = (
        neck_score(float(flexion), side_bent=False)
        if flexion_evaluated else None
    )
    score = (
        min(
            7,
            neck_base
            + int(side_bent)
            + int(shoulder_asymmetric)
            + int(sustained),
        )
        if neck_base is not None and lateral_evaluated and shoulder_evaluated
        else None
    )

    return {
        "contract_version": RULA_CONTRACT_VERSION,
        "status": "EVALUATED" if score is not None else "NOT_EVALUATED",
        "method": "RULA_ADAPTED_FRONT_V1",
        "source": "FRONT_CAMERA",
        "score": score,
        "risk_level": _risk_level(score) if score is not None else None,
        "components": {
            "neck_base": neck_base,
            "neck_side_bending": int(side_bent) if lateral_evaluated else None,
            "shoulder_asymmetry": (
                int(shoulder_asymmetric) if shoulder_evaluated else None
            ),
            "sustained_posture": int(sustained),
        },
        "neck_flexion_deg": float(flexion) if flexion_evaluated else None,
        "neck_side_bent": side_bent if lateral_evaluated else None,
        "shoulder_asymmetric": (
            shoulder_asymmetric if shoulder_evaluated else None
        ),
        "static_over_60_seconds": static_seconds > 60,
        "static_seconds": static_seconds,
        "limitations": [
            "Designed for a single front-facing camera.",
            "Shoulder asymmetry is a PostGuard adjustment, not an official RULA item.",
            "This is a RULA-adapted risk score, not Full RULA.",
        ],
    }
