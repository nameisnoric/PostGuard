import math


# ==========================================================
# Relative Neck Rotation
# ==========================================================

TORSO_MAPPING_K = -1.6409

RELATIVE_NECK_ROTATION_VERSION = "1.0"

CANDIDATE_STATUS = "candidate_prototype"


def _is_finite_number(value):
    """
    Return True only for a usable finite numeric value.
    """

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError):
        return False


def _invalid_result(reason):
    """
    Build a consistent invalid-result contract.
    """

    return {
        "valid": False,
        "reason": reason,
        "value": None,
        "relative_neck_rotation": None,
        "head_delta": None,
        "torso_delta": None,
        "torso_equivalent": None,
        "mapping_k": float(TORSO_MAPPING_K),
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
    """
    Calculate head rotation relative to torso orientation.

    Formula:

        head_delta
            = head_yaw - head_baseline

        torso_delta
            = torso_angle - torso_baseline

        torso_equivalent
            = k * torso_delta

        relative_neck_rotation
            = head_delta - torso_equivalent

    Important:
    - This is not a Risk score.
    - This is not RULA.
    - This does not define a risk threshold.
    - TORSO_MAPPING_K is still a prototype mapping candidate.
    """

    values = (
        head_yaw,
        torso_angle,
        head_baseline,
        torso_baseline,
        k,
    )

    # ======================================================
    # 1. Validate input
    # ======================================================

    if not all(
        _is_finite_number(value)
        for value in values
    ):
        return _invalid_result(
            "INVALID_INPUT"
        )

    head_yaw = float(head_yaw)
    torso_angle = float(torso_angle)
    head_baseline = float(head_baseline)
    torso_baseline = float(torso_baseline)
    k = float(k)

    # ======================================================
    # 2. Head delta
    # ======================================================

    head_delta = (
        head_yaw
        -
        head_baseline
    )

    # ======================================================
    # 3. Torso delta
    # ======================================================

    torso_delta = (
        torso_angle
        -
        torso_baseline
    )

    # ======================================================
    # 4. Convert torso movement to head-yaw-equivalent scale
    # ======================================================

    torso_equivalent = (
        k
        *
        torso_delta
    )

    # ======================================================
    # 5. Relative neck rotation
    # ======================================================

    relative_neck_rotation = (
        head_delta
        -
        torso_equivalent
    )

    # ======================================================
    # 6. Defensive output validation
    # ======================================================

    if not all(
        _is_finite_number(value)
        for value in (
            head_delta,
            torso_delta,
            torso_equivalent,
            relative_neck_rotation,
        )
    ):
        return _invalid_result(
            "CALCULATION_INVALID"
        )

    # ======================================================
    # 7. Contract
    # ======================================================

    return {
        "valid": True,
        "reason": "OK",

        "value": float(
            relative_neck_rotation
        ),

        "relative_neck_rotation": float(
            relative_neck_rotation
        ),

        "head_delta": float(
            head_delta
        ),

        "torso_delta": float(
            torso_delta
        ),

        "torso_equivalent": float(
            torso_equivalent
        ),

        "mapping_k": float(k),

        "unit": "deg",

        "status": CANDIDATE_STATUS,

        "version": RELATIVE_NECK_ROTATION_VERSION,
    }