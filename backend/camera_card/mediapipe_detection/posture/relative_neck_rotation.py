import math


# ==========================================================
# Torso Mapping
#
# IMPORTANT:
# ถ้า Torso Orientation formula เปลี่ยน
# ค่า K ต้อง Re-calibrate ใหม่
# ==========================================================

TORSO_MAPPING_K = -1.6409


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(
    value
):

    try:

        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):

        return False


# ==========================================================
# Relative Neck Rotation
# ==========================================================

def calculate_relative_neck_rotation(
    current_head_yaw,
    baseline_head_yaw,
    current_torso_angle,
    baseline_torso_angle,
    k=TORSO_MAPPING_K,
):
    """
    Relative Neck Rotation


    Head Delta

        current_head_yaw
        -
        baseline_head_yaw


    Torso Delta

        current_torso_angle
        -
        baseline_torso_angle


    Torso Equivalent

        k
        *
        torso_delta


    Relative Neck Rotation

        head_delta
        -
        torso_equivalent


    NOTE

    TORSO_MAPPING_K
    ต้อง Calibration ตาม
    Torso Orientation implementation
    ที่ใช้งานจริง
    """

    # ======================================================
    # 1. Validate Inputs
    # ======================================================

    values = (

        current_head_yaw,

        baseline_head_yaw,

        current_torso_angle,

        baseline_torso_angle,

        k,
    )


    if not all(

        _is_finite_number(
            value
        )

        for value in values
    ):

        return {

            "valid": False,

            "reason": (
                "invalid_input"
            ),

            "value": None,

            "unit": (
                "deg"
            ),

            "status": (
                "candidate_prototype"
            ),
        }


    # ======================================================
    # 2. Head Delta
    # ======================================================

    head_delta = (

        float(
            current_head_yaw
        )

        -

        float(
            baseline_head_yaw
        )
    )


    # ======================================================
    # 3. Torso Delta
    # ======================================================

    torso_delta = (

        float(
            current_torso_angle
        )

        -

        float(
            baseline_torso_angle
        )
    )


    # ======================================================
    # 4. Torso Equivalent
    # ======================================================

    torso_equivalent = (

        float(
            k
        )

        *

        torso_delta
    )


    # ======================================================
    # 5. Relative Neck Rotation
    # ======================================================

    relative_neck_rotation = (

        head_delta

        -

        torso_equivalent
    )


    # ======================================================
    # 6. Return
    # ======================================================

    return {

        "valid": True,

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

        "mapping_k": float(
            k
        ),

        "unit": (
            "deg"
        ),

        "status": (
            "candidate_prototype"
        ),
    }