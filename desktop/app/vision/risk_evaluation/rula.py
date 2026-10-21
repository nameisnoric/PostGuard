"""RULA scoring primitives and full Table A/B/C calculation.

Sources:
- McAtamney & Corlett (1993), Applied Ergonomics 24(2), 91-99.
  DOI: 10.1016/0003-6870(93)90080-S
- Cornell RULA Employee Assessment Worksheet (Alan Hedge, 2000).

The full score is returned only when every required observation is supplied.
Camera-derived partial results must never be presented as a Full RULA score.
"""

from __future__ import annotations

import math
from collections.abc import Mapping


RULA_CONTRACT_VERSION = "1.0"

# Table A columns are wrist 1/twist 1, wrist 1/twist 2, ... wrist 4/twist 2.
TABLE_A = (
    ((1, 2, 2, 2, 2, 3, 3, 3), (2, 2, 2, 2, 3, 3, 3, 3), (2, 3, 3, 3, 3, 3, 4, 4)),
    ((2, 3, 3, 3, 3, 4, 4, 4), (3, 3, 3, 3, 3, 4, 4, 4), (3, 4, 4, 4, 4, 4, 5, 5)),
    ((3, 3, 4, 4, 4, 4, 5, 5), (3, 4, 4, 4, 4, 4, 5, 5), (4, 4, 4, 4, 4, 5, 5, 5)),
    ((4, 4, 4, 4, 4, 5, 5, 5), (4, 4, 4, 4, 4, 5, 5, 5), (4, 4, 4, 5, 5, 5, 6, 6)),
    ((5, 5, 5, 5, 5, 6, 6, 7), (5, 6, 6, 6, 6, 7, 7, 7), (6, 6, 6, 7, 7, 7, 7, 8)),
    ((7, 7, 7, 7, 7, 8, 8, 9), (8, 8, 8, 8, 8, 9, 9, 9), (9, 9, 9, 9, 9, 9, 9, 9)),
)

# Table B columns are trunk 1/legs 1, trunk 1/legs 2, ... trunk 6/legs 2.
TABLE_B = (
    (1, 3, 2, 3, 3, 4, 5, 5, 6, 6, 7, 7),
    (2, 3, 2, 3, 4, 5, 5, 5, 6, 7, 7, 7),
    (3, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 7),
    (5, 5, 5, 6, 6, 7, 7, 7, 7, 7, 8, 8),
    (7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8),
    (8, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9),
)

# Table C rows are final wrist/arm score 1..8+; columns are B score 1..7+.
TABLE_C = (
    (1, 2, 3, 3, 4, 5, 5),
    (2, 2, 3, 4, 4, 5, 5),
    (3, 3, 3, 4, 4, 5, 6),
    (3, 3, 3, 4, 5, 6, 6),
    (4, 4, 4, 5, 6, 7, 7),
    (4, 4, 5, 6, 6, 7, 7),
    (5, 5, 6, 6, 7, 7, 7),
    (5, 5, 6, 7, 7, 7, 7),
)


class RulaInputError(ValueError):
    """Raised when a RULA observation is outside its defined domain."""


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RulaInputError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise RulaInputError(f"{name} must be a finite number")
    return value


def _score(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise RulaInputError(f"{name} must be {minimum}..{maximum}")
    return value


def _flag(value, name):
    if type(value) is not bool:
        raise RulaInputError(f"{name} must be boolean")
    return value


def upper_arm_score(
    angle_deg,
    *,
    shoulder_raised=False,
    abducted=False,
    supported=False,
):
    """Score upper-arm flexion (+) or extension (-), including adjustments."""
    angle = _number(angle_deg, "upper_arm_angle_deg")
    if angle < -20:
        score = 2
    elif angle <= 20:
        score = 1
    elif angle <= 45:
        score = 2
    elif angle <= 90:
        score = 3
    else:
        score = 4
    score += int(_flag(shoulder_raised, "shoulder_raised"))
    score += int(_flag(abducted, "abducted"))
    score -= int(_flag(supported, "supported"))
    return min(6, max(1, score))


def lower_arm_score(angle_deg, *, across_midline_or_outside=False):
    angle = _number(angle_deg, "lower_arm_angle_deg")
    score = 1 if 60 <= angle <= 100 else 2
    score += int(_flag(across_midline_or_outside, "across_midline_or_outside"))
    return min(3, score)


def wrist_score(angle_deg, *, deviated=False):
    angle = abs(_number(angle_deg, "wrist_angle_deg"))
    if angle == 0:
        score = 1
    elif angle <= 15:
        score = 2
    else:
        score = 3
    score += int(_flag(deviated, "deviated"))
    return min(4, score)


def wrist_twist_score(near_end_range):
    return 2 if _flag(near_end_range, "near_end_range") else 1


def neck_score(flexion_deg, *, twisted=False, side_bent=False):
    """Score neck flexion (+) or extension (-), including RULA adjustments."""
    angle = _number(flexion_deg, "neck_flexion_deg")
    if angle < 0:
        score = 4
    elif angle <= 10:
        score = 1
    elif angle <= 20:
        score = 2
    else:
        score = 3
    score += int(_flag(twisted, "twisted"))
    score += int(_flag(side_bent, "side_bent"))
    return min(6, score)


def trunk_score(flexion_deg, *, twisted=False, side_bent=False):
    angle = _number(flexion_deg, "trunk_flexion_deg")
    if angle <= 0:
        score = 1
    elif angle <= 20:
        score = 2
    elif angle <= 60:
        score = 3
    else:
        score = 4
    score += int(_flag(twisted, "twisted"))
    score += int(_flag(side_bent, "side_bent"))
    return min(6, score)


def legs_score(supported_and_balanced):
    return 1 if _flag(supported_and_balanced, "supported_and_balanced") else 2


def muscle_use_score(*, static_seconds=0.0, repetitions_per_minute=0.0):
    seconds = _number(static_seconds, "static_seconds")
    repetitions = _number(repetitions_per_minute, "repetitions_per_minute")
    if seconds < 0 or repetitions < 0:
        raise RulaInputError("muscle-use inputs cannot be negative")
    return int(seconds > 60 or repetitions >= 4)


def force_load_score(load_kg, *, static_or_repeated=False, shock=False):
    load = _number(load_kg, "load_kg")
    if load < 0:
        raise RulaInputError("load_kg cannot be negative")
    repeated = _flag(static_or_repeated, "static_or_repeated")
    shock = _flag(shock, "shock")
    if shock or load > 10:
        return 3
    if repeated and load >= 2:
        return 2
    if load >= 2:
        return 1
    return 0


def table_a_score(upper_arm, lower_arm, wrist, wrist_twist):
    upper_arm = _score(upper_arm, "upper_arm_score", 1, 6)
    lower_arm = _score(lower_arm, "lower_arm_score", 1, 3)
    wrist = _score(wrist, "wrist_score", 1, 4)
    wrist_twist = _score(wrist_twist, "wrist_twist_score", 1, 2)
    column = (wrist - 1) * 2 + wrist_twist - 1
    return TABLE_A[upper_arm - 1][lower_arm - 1][column]


def table_b_score(neck, trunk, legs):
    neck = _score(neck, "neck_score", 1, 6)
    trunk = _score(trunk, "trunk_score", 1, 6)
    legs = _score(legs, "legs_score", 1, 2)
    column = (trunk - 1) * 2 + legs - 1
    return TABLE_B[neck - 1][column]


def table_c_score(final_a, final_b):
    final_a = _score(final_a, "final_a", 1, 13)
    final_b = _score(final_b, "final_b", 1, 13)
    return TABLE_C[min(final_a, 8) - 1][min(final_b, 7) - 1]


def action_level(final_score):
    final_score = _score(final_score, "final_score", 1, 7)
    if final_score <= 2:
        return 1, "ACCEPTABLE"
    if final_score <= 4:
        return 2, "INVESTIGATE_CHANGE_MAY_BE_NEEDED"
    if final_score <= 6:
        return 3, "INVESTIGATE_AND_CHANGE_SOON"
    return 4, "INVESTIGATE_AND_CHANGE_IMMEDIATELY"


def assess_full_rula(observations: Mapping):
    """Calculate Full RULA when every scored observation is available."""
    if not isinstance(observations, Mapping):
        raise RulaInputError("observations must be a mapping")
    required = {
        "upper_arm", "lower_arm", "wrist", "wrist_twist",
        "neck", "trunk", "legs", "muscle_use_a", "force_load_a",
        "muscle_use_b", "force_load_b",
    }
    missing = sorted(required - observations.keys())
    if missing:
        return {
            "contract_version": RULA_CONTRACT_VERSION,
            "status": "PARTIAL",
            "missing": missing,
            "final_score": None,
            "action_level": None,
            "action": None,
        }

    group_a = table_a_score(
        observations["upper_arm"], observations["lower_arm"],
        observations["wrist"], observations["wrist_twist"],
    )
    group_b = table_b_score(
        observations["neck"], observations["trunk"], observations["legs"]
    )
    muscle_a = _score(observations["muscle_use_a"], "muscle_use_a", 0, 1)
    force_a = _score(observations["force_load_a"], "force_load_a", 0, 3)
    muscle_b = _score(observations["muscle_use_b"], "muscle_use_b", 0, 1)
    force_b = _score(observations["force_load_b"], "force_load_b", 0, 3)
    final_a = group_a + muscle_a + force_a
    final_b = group_b + muscle_b + force_b
    final_score = table_c_score(final_a, final_b)
    level, action = action_level(final_score)
    return {
        "contract_version": RULA_CONTRACT_VERSION,
        "status": "COMPLETE",
        "missing": [],
        "posture_score_a": group_a,
        "posture_score_b": group_b,
        "final_score_a": final_a,
        "final_score_b": final_b,
        "final_score": final_score,
        "action_level": level,
        "action": action,
    }


def camera_rula_partial(assessment_result: Mapping, temporal_result: Mapping):
    """Return the RULA observations supported by the current camera contract."""
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
    neck_lower_bound = (
        neck_score(float(flexion), twisted=False, side_bent=side_bent)
        if flexion_evaluated and lateral_evaluated
        else None
    )
    static_seconds = max(duration_rows, default=0.0)
    muscle_use = muscle_use_score(static_seconds=static_seconds)
    missing = [
        "neck_twist", "upper_arm", "lower_arm", "wrist", "wrist_twist",
        "trunk", "legs", "force_load",
    ]
    if not flexion_evaluated:
        missing.append("neck_flexion")
    if not lateral_evaluated:
        missing.append("neck_side_bending")
    return {
        "contract_version": RULA_CONTRACT_VERSION,
        "status": "PARTIAL",
        "supported": False,
        "source": "CAMERA_DERIVED",
        "neck_score_lower_bound": neck_lower_bound,
        "neck_flexion_deg": float(flexion) if flexion_evaluated else None,
        "neck_side_bent": side_bent if lateral_evaluated else None,
        "muscle_use_score": muscle_use,
        "static_seconds": static_seconds,
        "missing": sorted(missing),
        "final_score": None,
        "action_level": None,
        "action": None,
        "limitations": [
            "Neck twist is not measured by the current Detection Contract.",
            "Full RULA requires arm, wrist, trunk, leg and force/load observations.",
        ],
    }
