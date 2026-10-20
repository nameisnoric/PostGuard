import math


# ==========================================================
# Required Points by Feature
#
# แต่ละ Feature ใช้ Landmark ไม่เหมือนกัน
# จึงไม่ควรใช้ Validator ชุดเดียวบังคับทุก Feature
# ==========================================================

HEAD_ORIENTATION_POINTS = (
    "nose_tip",
    "chin",

    "right_eye_outer",
    "right_eye_inner",

    "left_eye_outer",
    "left_eye_inner",

    "right_face",
    "left_face",
)


RIGHT_EYE_POINTS = (
    "right_eye_outer",
    "right_eye_inner",
    "right_eye_upper",
    "right_eye_lower",
)


LEFT_EYE_POINTS = (
    "left_eye_outer",
    "left_eye_inner",
    "left_eye_upper",
    "left_eye_lower",
)


# ==========================================================
# Helper: ตรวจว่าเป็นตัวเลขที่ใช้งานได้
# ==========================================================

def _is_finite_number(
    value
):

    if value is None:
        return False


    try:

        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):

        return False


# ==========================================================
# Helper: Validate Point
# ==========================================================

def _validate_point(
    point
):

    # ------------------------------------------------------
    # ไม่มี Point
    # ------------------------------------------------------

    if point is None:

        return {
            "valid": False,
            "reason": "POINT_MISSING",
        }


    # ------------------------------------------------------
    # ต้องมีข้อมูลพื้นฐาน
    # ------------------------------------------------------

    required_keys = (
        "x_norm",
        "y_norm",
        "z",
        "x",
        "y",
    )


    for key in required_keys:

        if key not in point:

            return {
                "valid": False,
                "reason": (
                    f"MISSING_{key.upper()}"
                ),
            }


    # ------------------------------------------------------
    # ค่าต้องเป็น finite number
    #
    # ป้องกัน:
    # NaN
    # inf
    # None
    # ------------------------------------------------------

    if not _is_finite_number(
        point["x_norm"]
    ):

        return {
            "valid": False,
            "reason": "INVALID_X_NORM",
        }


    if not _is_finite_number(
        point["y_norm"]
    ):

        return {
            "valid": False,
            "reason": "INVALID_Y_NORM",
        }


    if not _is_finite_number(
        point["z"]
    ):

        return {
            "valid": False,
            "reason": "INVALID_Z",
        }


    if not _is_finite_number(
        point["x"]
    ):

        return {
            "valid": False,
            "reason": "INVALID_X_PIXEL",
        }


    if not _is_finite_number(
        point["y"]
    ):

        return {
            "valid": False,
            "reason": "INVALID_Y_PIXEL",
        }


    # ------------------------------------------------------
    # Face Landmark x/y เป็น normalized coordinate
    #
    # ถ้าออกนอก 0..1
    # แปลว่าจุดอยู่นอกขอบภาพ
    # ------------------------------------------------------

    if not (
        0.0
        <= point["x_norm"]
        <= 1.0
    ):

        return {
            "valid": False,
            "reason": "X_OUT_OF_FRAME",
        }


    if not (
        0.0
        <= point["y_norm"]
        <= 1.0
    ):

        return {
            "valid": False,
            "reason": "Y_OUT_OF_FRAME",
        }


    # ------------------------------------------------------
    # ผ่าน
    # ------------------------------------------------------

    return {
        "valid": True,
        "reason": "OK",
    }


# ==========================================================
# Generic Feature Validator
# ==========================================================

def _validate_required_points(
    points,
    required_points
):

    # ------------------------------------------------------
    # ไม่มี Selected Points
    # ------------------------------------------------------

    if points is None:

        return {
            "valid": False,
            "reason": "NO_FACE_POINTS",
            "invalid_points": [],
        }


    invalid_points = []


    # ------------------------------------------------------
    # ตรวจทุก Landmark ที่ Feature ต้องใช้
    # ------------------------------------------------------

    for name in required_points:

        if name not in points:

            invalid_points.append(
                {
                    "name": name,
                    "reason": "MISSING",
                }
            )

            continue


        result = _validate_point(
            points[name]
        )


        if not result["valid"]:

            invalid_points.append(
                {
                    "name": name,
                    "reason": result["reason"],
                }
            )


    # ------------------------------------------------------
    # มี Point ที่ใช้ไม่ได้
    # ------------------------------------------------------

    if invalid_points:

        return {
            "valid": False,
            "reason": "REQUIRED_POINTS_INVALID",
            "invalid_points": invalid_points,
        }


    # ------------------------------------------------------
    # ผ่าน
    # ------------------------------------------------------

    return {
        "valid": True,
        "reason": "OK",
        "invalid_points": [],
    }


# ==========================================================
# Head Orientation Validator
# ==========================================================

def validate_head_orientation(
    points
):

    return _validate_required_points(
        points,
        HEAD_ORIENTATION_POINTS
    )


# ==========================================================
# Right Eye Validator
# ==========================================================

def validate_right_eye(
    points
):

    return _validate_required_points(
        points,
        RIGHT_EYE_POINTS
    )


# ==========================================================
# Left Eye Validator
# ==========================================================

def validate_left_eye(
    points
):

    return _validate_required_points(
        points,
        LEFT_EYE_POINTS
    )


# ==========================================================
# Eye / Blink Validator
#
# Blink ใช้ตาทั้งสองข้าง
# แต่คืนผลแต่ละข้างแยกไว้ด้วย
# ==========================================================

def validate_eye_points(
    points
):

    right_eye = validate_right_eye(
        points
    )

    left_eye = validate_left_eye(
        points
    )


    valid = (
        right_eye["valid"]
        and left_eye["valid"]
    )


    if valid:

        reason = "OK"

    else:

        reason = "EYE_POINTS_INVALID"


    return {
        "valid": valid,
        "reason": reason,

        "right_eye": right_eye,
        "left_eye": left_eye,
    }