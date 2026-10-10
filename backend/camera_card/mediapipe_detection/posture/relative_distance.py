import math


# ==========================================================
# Inter-Eye Distance / IPD Proxy
# ==========================================================
#
# หน้าที่ของไฟล์นี้ตอนนี้:
#
# Face Eye Corner Landmarks
#          ↓
# Left Eye Center
# Right Eye Center
#          ↓
# eye_distance_px
#
# IMPORTANT:
#
# eye_distance_px ไม่ใช่ physical/anatomical IPD
# เพราะเราไม่ได้ใช้ pupil center จริง
#
# เป็น Inter-Eye Distance / IPD Proxy
# จาก inner + outer eye corners
#
# ไฟล์นี้ยังไม่คำนวณ:
#
# - Personal Baseline
# - Relative Distance
# - Risk
# - RULA
# - Alert
# ==========================================================


# ==========================================================
# Helper: Finite Number
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่าค่าเป็นตัวเลขปกติหรือไม่

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - String ที่แปลงไม่ได้
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


# ==========================================================
# Helper: Get Pixel XY
# ==========================================================

def _get_xy(point):
    """
    ดึง pixel x/y จาก Face Landmark

    Expected format:

        {
            "x": ...,
            "y": ...
        }

    ใน PostGuard:
        x/y เป็น pixel coordinates อยู่แล้ว
    """

    if point is None:
        return None


    try:

        x = float(
            point["x"]
        )

        y = float(
            point["y"]
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):

        return None


    if (
        not _is_finite_number(x)
        or
        not _is_finite_number(y)
    ):

        return None


    return (
        x,
        y
    )


# ==========================================================
# Helper: Midpoint
# ==========================================================

def _calculate_midpoint(
    point_a,
    point_b
):
    """
    คำนวณ midpoint ระหว่างจุด 2 จุดในภาพ
    """

    if (
        point_a is None
        or point_b is None
    ):

        return None


    midpoint_x = (
        point_a[0]
        +
        point_b[0]
    ) / 2.0


    midpoint_y = (
        point_a[1]
        +
        point_b[1]
    ) / 2.0


    return (
        midpoint_x,
        midpoint_y
    )


# ==========================================================
# Candidate Prototype Measurement:
# Inter-Eye Distance / IPD Proxy
# ==========================================================

def calculate_eye_distance(
    face_points
):
    """
    Calculate Inter-Eye Distance in pixels.

    Required Face Landmarks:

        left_eye_outer
        left_eye_inner

        right_eye_inner
        right_eye_outer

    Eye centers:

        Left Eye Center
            = midpoint(
                left_eye_outer,
                left_eye_inner
              )

        Right Eye Center
            = midpoint(
                right_eye_inner,
                right_eye_outer
              )

    Measurement:

        eye_distance_px
            = Euclidean Distance(
                left_eye_center,
                right_eye_center
              )

    Expected behavior:

        Move closer to camera
            -> eye_distance_px increases

        Move farther from camera
            -> eye_distance_px decreases

    IMPORTANT:

    This is NOT anatomical pupil-to-pupil IPD.

    It is a pixel-based Inter-Eye Distance
    used as an IPD Proxy.

    This function does NOT calculate:
    - Personal Baseline
    - Relative Distance
    - Risk
    - RULA
    - Alert
    """

    # ======================================================
    # 1. Validate face_points
    # ======================================================

    if face_points is None:
        return None


    # ======================================================
    # 2. Required Eye Corner Points
    # ======================================================

    try:

        left_outer_raw = (
            face_points.get(
                "left_eye_outer"
            )
        )

        left_inner_raw = (
            face_points.get(
                "left_eye_inner"
            )
        )

        right_inner_raw = (
            face_points.get(
                "right_eye_inner"
            )
        )

        right_outer_raw = (
            face_points.get(
                "right_eye_outer"
            )
        )

    except AttributeError:

        return None


    # ======================================================
    # 3. Convert to pixel XY
    # ======================================================

    left_eye_outer = _get_xy(
        left_outer_raw
    )


    left_eye_inner = _get_xy(
        left_inner_raw
    )


    right_eye_inner = _get_xy(
        right_inner_raw
    )


    right_eye_outer = _get_xy(
        right_outer_raw
    )


    required_points = (
        left_eye_outer,
        left_eye_inner,
        right_eye_inner,
        right_eye_outer,
    )


    if any(
        point is None
        for point in required_points
    ):

        return None


    # ======================================================
    # 4. Left Eye Center
    # ======================================================

    left_eye_center = (
        _calculate_midpoint(
            left_eye_outer,
            left_eye_inner
        )
    )


    # ======================================================
    # 5. Right Eye Center
    # ======================================================

    right_eye_center = (
        _calculate_midpoint(
            right_eye_inner,
            right_eye_outer
        )
    )


    if (
        left_eye_center is None
        or right_eye_center is None
    ):

        return None


    # ======================================================
    # 6. Inter-Eye Difference
    # ======================================================

    dx = (
        right_eye_center[0]
        -
        left_eye_center[0]
    )


    dy = (
        right_eye_center[1]
        -
        left_eye_center[1]
    )


    # ======================================================
    # 7. Euclidean Pixel Distance
    # ======================================================

    eye_distance_px = math.sqrt(
        dx ** 2
        +
        dy ** 2
    )


    # ======================================================
    # 8. Validate Result
    # ======================================================

    if (
        not _is_finite_number(
            eye_distance_px
        )
        or
        eye_distance_px <= 1e-6
    ):

        return None


    # ======================================================
    # 9. Return
    # ======================================================

    return {

        "left_eye_center": (
            left_eye_center
        ),

        "right_eye_center": (
            right_eye_center
        ),

        "eye_distance_px": float(
            eye_distance_px
        ),
    }