import math


def _is_finite_number(value):

    try:
        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):
        return False


def calculate_torso_orientation(
    points
):
    """
    Experimental torso orientation metric.

    Uses Pose World Landmarks:
    - left_shoulder
    - right_shoulder

    Calculates shoulder depth angle in X-Z plane.

    This is NOT:
    - Risk
    - RULA
    - Personal Baseline
    - Final Neck Rotation

    It is currently a torso rotation candidate.
    """

    # ======================================================
    # 1. Check points
    # ======================================================

    if points is None:
        return None


    required_points = (
        "left_shoulder",
        "right_shoulder",
    )


    for name in required_points:

        if name not in points:
            return None


    left = points[
        "left_shoulder"
    ]

    right = points[
        "right_shoulder"
    ]


    # ======================================================
    # 2. Required world coordinates
    # ======================================================

    required_values = (
        "world_x",
        "world_y",
        "world_z",
    )


    for key in required_values:

        if (
            key not in left
            or
            key not in right
        ):
            return None


        if not _is_finite_number(
            left[key]
        ):
            return None


        if not _is_finite_number(
            right[key]
        ):
            return None


    # ======================================================
    # 3. Shoulder vector
    #
    # Left Shoulder -> Right Shoulder
    # ======================================================

    dx = (
        right["world_x"]
        -
        left["world_x"]
    )


    dy = (
        right["world_y"]
        -
        left["world_y"]
    )


    dz = (
        right["world_z"]
        -
        left["world_z"]
    )


    # ======================================================
    # 4. Protect invalid shoulder width
    # ======================================================

    horizontal_width = abs(
        dx
    )


    if horizontal_width < 1e-6:
        return None


    # ======================================================
    # 5. Shoulder Depth Angle
    #
    # Torso facing camera:
    # dz should be relatively small
    #
    # Torso rotates:
    # one shoulder moves deeper / closer
    #
    # Sign convention will be learned from experiment.
    # ======================================================

    angle_rad = math.atan2(
        dz,
        horizontal_width
    )


    angle_deg = math.degrees(
        angle_rad
    )


    # ======================================================
    # 6. Diagnostic values
    # ======================================================

    width_xz = math.sqrt(
        dx * dx
        +
        dz * dz
    )


    width_3d = math.sqrt(
        dx * dx
        +
        dy * dy
        +
        dz * dz
    )


    return {

        "angle": float(
            angle_deg
        ),

        "world_dx": float(
            dx
        ),

        "world_dy": float(
            dy
        ),

        "world_dz": float(
            dz
        ),

        "width_xz": float(
            width_xz
        ),

        "width_3d": float(
            width_3d
        ),
    }