import math


# ==========================================================
# Pose Landmark Quality Threshold
# ==========================================================

MIN_VISIBILITY = 0.6
MIN_PRESENCE = 0.6


# ==========================================================
# Helper
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่า value เป็นตัวเลขที่ใช้งานได้

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - String
    """

    if value is None:
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError):
        return False


# ==========================================================
# Validate Single Pose Point
# ==========================================================

def _validate_pose_point(
    point,
    require_world=False
):
    """
    Validate Landmark เพียง 1 จุด

    Parameters
    ----------
    point:
        landmark dictionary

    require_world:
        True ถ้า Feature ต้องใช้
        world_x / world_y / world_z
    """

    if point is None:
        return {
            "valid": False,
            "reason": "POINT_MISSING"
        }

    # ------------------------------------------------------
    # Image Coordinates
    # ------------------------------------------------------

    required_image_values = (
        "x",
        "y",
        "visibility",
        "presence",
    )

    for key in required_image_values:

        if key not in point:
            return {
                "valid": False,
                "reason": f"MISSING_{key.upper()}"
            }

        if not _is_finite_number(point[key]):
            return {
                "valid": False,
                "reason": f"INVALID_{key.upper()}"
            }

    # ------------------------------------------------------
    # Landmark Quality
    # ------------------------------------------------------

    if float(point["visibility"]) < MIN_VISIBILITY:
        return {
            "valid": False,
            "reason": "LOW_VISIBILITY"
        }

    if float(point["presence"]) < MIN_PRESENCE:
        return {
            "valid": False,
            "reason": "LOW_PRESENCE"
        }

    # ------------------------------------------------------
    # World Coordinates
    # ------------------------------------------------------

    if require_world:

        for key in (
            "world_x",
            "world_y",
            "world_z",
        ):

            if key not in point:
                return {
                    "valid": False,
                    "reason": f"MISSING_{key.upper()}"
                }

            if not _is_finite_number(point[key]):
                return {
                    "valid": False,
                    "reason": f"INVALID_{key.upper()}"
                }

    return {
        "valid": True,
        "reason": "OK"
    }


# ==========================================================
# Generic Feature Validator
# ==========================================================

def validate_pose_feature(
    pose_points,
    required_points,
    require_world=False
):
    """
    Validate Landmark ตาม Feature

    แต่ละ Feature ใช้ Landmark ไม่เหมือนกัน
    จึงไม่ควรใช้ pose_valid ตัวเดียวกับทุก Feature
    """

    if pose_points is None:

        return {
            "valid": False,
            "reason": "POSE_NOT_FOUND",
            "invalid_points": []
        }

    invalid_points = []

    invalid_reasons = {}

    for name in required_points:

        point = pose_points.get(name)

        result = _validate_pose_point(
            point,
            require_world=require_world
        )

        if not result["valid"]:

            invalid_points.append(name)

            invalid_reasons[name] = (
                result["reason"]
            )

    if invalid_points:

        return {
            "valid": False,
            "reason": "LANDMARK_INVALID",
            "invalid_points": invalid_points,
            "invalid_reasons": invalid_reasons
        }

    return {
        "valid": True,
        "reason": "OK",
        "invalid_points": [],
        "invalid_reasons": {}
    }


# ==========================================================
# Shoulder Tilt
# ==========================================================

def validate_shoulder_tilt(
    pose_points
):

    return validate_pose_feature(
        pose_points,
        required_points=(
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=False
    )


# ==========================================================
# Shoulder Elevation
# ==========================================================

def validate_shoulder_elevation(
    pose_points
):

    return validate_pose_feature(
        pose_points,
        required_points=(
            "nose",
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=False
    )


# ==========================================================
# Neck Lateral Tilt
# ==========================================================

def validate_neck_lateral_tilt(
    pose_points
):

    return validate_pose_feature(
        pose_points,
        required_points=(
            "left_ear",
            "right_ear",
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=False
    )


# ==========================================================
# Forward Head
# ==========================================================

def validate_forward_head(
    pose_points
):

    return validate_pose_feature(
        pose_points,
        required_points=(
            "nose",
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=True
    )


# ==========================================================
# Torso Orientation
# ==========================================================

def validate_torso_orientation(
    pose_points
):

    return validate_pose_feature(
        pose_points,
        required_points=(
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=True
    )


# ==========================================================
# Legacy General Validator
# ==========================================================

def validate_pose_points(
    pose_points
):
    """
    เก็บไว้เพื่อไม่ให้โค้ดเก่าที่เรียก
    validate_pose_points() พัง

    IMPORTANT:
    ห้ามใช้ผลนี้แทน Validation
    ของทุก Feature
    """

    return validate_pose_feature(
        pose_points,
        required_points=(
            "nose",
            "left_shoulder",
            "right_shoulder",
        ),
        require_world=False
    )