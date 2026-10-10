import math


# ==========================================================
# Prototype Torso Mapping Factor
#
# Derived from:
# torso_rotation_validation_...
#
# Median candidate:
# k = -1.6409
#
# IMPORTANT:
# ตอนนี้ยังเป็น Prototype Mapping Candidate
# ไม่ถือว่าเป็นค่าถาวรของระบบ
# ==========================================================

TORSO_MAPPING_K = -1.6409


def _is_finite_number(value):
    """
    ตรวจว่าค่าเป็นตัวเลขที่ใช้งานได้หรือไม่
    """

    try:
        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):
        return False


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

        Head Delta
        = Current Head Yaw - Head Baseline

        Torso Delta
        = Current Torso Angle - Torso Baseline

        Torso Equivalent
        = k * Torso Delta

        Relative Neck Rotation
        = Head Delta - Torso Equivalent


    Example:

        Head Delta  = +30
        Torso Delta = 0

        Relative ≈ +30

        => Head rotated relative to torso


    Another example:

        Head Delta  = +30
        Torso Delta = -18.3
        k            = -1.6409

        Torso Equivalent ≈ +30

        Relative ≈ 0

        => Head and torso rotated together


    This file does NOT contain:

    - Risk thresholds
    - RULA
    - Alert logic
    - Personal Baseline collection
    """

    values = (
        head_yaw,
        torso_angle,
        head_baseline,
        torso_baseline,
        k,
    )


    # ======================================================
    # Validate input
    # ======================================================

    if not all(
        _is_finite_number(value)
        for value in values
    ):
        return None


    # ======================================================
    # Head movement relative to neutral/reference
    # ======================================================

    head_delta = (
        float(head_yaw)
        -
        float(head_baseline)
    )


    # ======================================================
    # Torso movement relative to neutral/reference
    # ======================================================

    torso_delta = (
        float(torso_angle)
        -
        float(torso_baseline)
    )


    # ======================================================
    # Convert torso signal into head-yaw-equivalent scale
    # ======================================================

    torso_equivalent = (
        float(k)
        *
        torso_delta
    )


    # ======================================================
    # Head rotation relative to torso
    # ======================================================

    relative_neck_rotation = (
        head_delta
        -
        torso_equivalent
    )


    return {

        "head_delta": (
            head_delta
        ),

        "torso_delta": (
            torso_delta
        ),

        "torso_equivalent": (
            torso_equivalent
        ),

        "relative_neck_rotation": (
            relative_neck_rotation
        ),
    }