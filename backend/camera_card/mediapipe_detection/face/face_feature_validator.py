import math


def _is_finite_number(value):
    """
    ตรวจว่าค่าเป็น finite number
    """

    if value is None:
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError):
        return False


def validate_face_feature(
    face_points,
    required_points
):
    """
    Validate Face Landmark ตาม Feature

    Face Landmarker ไม่มี visibility/presence
    แบบ Pose Landmarker

    ดังนั้นตรวจ:
    - Point มีจริง
    - x / y มีจริง
    - normalized coordinate มีจริง
    - z ใช้งานได้
    """

    if face_points is None:

        return {
            "valid": False,
            "reason": "FACE_NOT_FOUND",
            "invalid_points": []
        }

    invalid_points = []

    invalid_reasons = {}

    for name in required_points:

        point = face_points.get(name)

        if point is None:

            invalid_points.append(name)

            invalid_reasons[name] = (
                "POINT_MISSING"
            )

            continue

        required_values = (
            "x",
            "y",
            "x_norm",
            "y_norm",
            "z",
        )

        point_valid = True

        for key in required_values:

            if (
                key not in point
                or not _is_finite_number(
                    point[key]
                )
            ):

                invalid_points.append(name)

                invalid_reasons[name] = (
                    f"INVALID_{key.upper()}"
                )

                point_valid = False

                break

        if not point_valid:
            continue

    if invalid_points:

        # ป้องกันชื่อซ้ำ
        invalid_points = list(
            dict.fromkeys(
                invalid_points
            )
        )

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