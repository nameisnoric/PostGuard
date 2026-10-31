"""Head rotation relative to torso orientation.

Adapted from ``integration/desktop-risk-pipeline`` while preserving the
prototype status of the torso mapping factor.
"""

from __future__ import annotations

import math


TORSO_MAPPING_K = -1.6409
RELATIVE_NECK_ROTATION_VERSION = "1.0"
CANDIDATE_STATUS = "candidate_prototype"


def _is_finite_number(value: object) -> bool:
    """Return whether *value* can be represented as a finite float."""
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _invalid_result(reason: str, *, mapping_k: object = TORSO_MAPPING_K) -> dict:
    """Build the stable result shape used when calculation is unavailable."""
    safe_mapping_k = (
        float(mapping_k) if _is_finite_number(mapping_k) else float(TORSO_MAPPING_K)
    )
    return {
        "valid": False,
        "reason": reason,
        "value": None,
        "relative_neck_rotation": None,
        "head_delta": None,
        "torso_delta": None,
        "torso_equivalent": None,
        "mapping_k": safe_mapping_k,
        "unit": "deg",
        "status": CANDIDATE_STATUS,
        "version": RELATIVE_NECK_ROTATION_VERSION,
    }


def calculate_relative_neck_rotation(
    head_yaw,
    torso_angle,
    head_baseline,
    torso_baseline,
    k=TORSO_MAPPING_K,
):
    """Calculate head rotation relative to the user's torso.

    ``head_delta`` is corrected by the torso movement converted to the same
    angular scale. This is an experimental measurement contract; it does not
    calculate a risk score or define a posture threshold.
    """
    values = (head_yaw, torso_angle, head_baseline, torso_baseline, k)
    if not all(_is_finite_number(value) for value in values):
        return _invalid_result("INVALID_INPUT", mapping_k=k)

    head_yaw = float(head_yaw)
    torso_angle = float(torso_angle)
    head_baseline = float(head_baseline)
    torso_baseline = float(torso_baseline)
    k = float(k)

    head_delta = head_yaw - head_baseline
    torso_delta = torso_angle - torso_baseline
    torso_equivalent = k * torso_delta
    relative_neck_rotation = head_delta - torso_equivalent

    outputs = (
        head_delta,
        torso_delta,
        torso_equivalent,
        relative_neck_rotation,
    )
    if not all(_is_finite_number(value) for value in outputs):
        return _invalid_result("CALCULATION_INVALID", mapping_k=k)

    return {
        "valid": True,
        "reason": "OK",
        "value": float(relative_neck_rotation),
        "relative_neck_rotation": float(relative_neck_rotation),
        "head_delta": float(head_delta),
        "torso_delta": float(torso_delta),
        "torso_equivalent": float(torso_equivalent),
        "mapping_k": k,
        "unit": "deg",
        "status": CANDIDATE_STATUS,
        "version": RELATIVE_NECK_ROTATION_VERSION,
    }
