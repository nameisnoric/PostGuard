import math


from mediapipe_detection.face.face_validator import (
    validate_eye_points
)


# ==========================================================
# Eye Openness Measurement
# ==========================================================
#
# PostGuard ใช้ Landmark ของตา 4 จุดต่อข้าง:
#
# outer
# inner
# upper
# lower
#
#
# สูตร:
#
#                    Vertical Eye Opening
# Eye Openness =     --------------------
#                    Horizontal Eye Width
#
#
# IMPORTANT:
#
# เราเรียกค่านี้ว่า:
#
# Eye Openness Ratio
#
# ไม่เรียกว่า Standard EAR
#
# เพราะ Standard EAR แบบดั้งเดิม
# ใช้จำนวน landmark รอบตามากกว่านี้
#
#
# Module นี้ทำหน้าที่เฉพาะ Measurement
#
# ยังไม่ทำ:
#
# - OPEN / CLOSED classification
# - Blink Detection
# - Blink Count
# - Eye Fatigue
# - Drowsiness
# - Alert
#
# ==========================================================


# ==========================================================
# Helper: Finite Number
# ==========================================================

def _is_finite_number(
    value
):
    """
    ตรวจว่าค่าเป็นตัวเลขที่ใช้งานได้

    ป้องกัน:
    - None
    - NaN
    - inf
    - string ที่แปลงไม่ได้
    """

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
# Helper: Get Pixel Coordinate
# ==========================================================

def _get_pixel_xy(
    point
):
    """
    รับ point จาก face_points.py

    Expected structure:

    {
        "id": ...,
        "x_norm": ...,
        "y_norm": ...,
        "z": ...,
        "x": pixel_x,
        "y": pixel_y,
    }

    สำหรับ Eye Openness เราใช้ x/y pixel
    """

    if point is None:
        return None


    if (
        "x" not in point
        or
        "y" not in point
    ):
        return None


    x = point[
        "x"
    ]


    y = point[
        "y"
    ]


    if (
        not _is_finite_number(
            x
        )
        or
        not _is_finite_number(
            y
        )
    ):
        return None


    return (
        float(x),
        float(y)
    )


# ==========================================================
# Helper: 2D Euclidean Distance
# ==========================================================

def _distance_2d(
    point_a,
    point_b
):
    """
    ระยะ Euclidean ระหว่าง 2 จุด

    distance =
    sqrt(
        dx^2
        +
        dy^2
    )
    """

    if (
        point_a is None
        or
        point_b is None
    ):
        return None


    dx = (
        point_b[0]
        -
        point_a[0]
    )


    dy = (
        point_b[1]
        -
        point_a[1]
    )


    distance = math.sqrt(
        (
            dx
            *
            dx
        )
        +
        (
            dy
            *
            dy
        )
    )


    if not _is_finite_number(
        distance
    ):
        return None


    return float(
        distance
    )


# ==========================================================
# Calculate One Eye
# ==========================================================

def _calculate_single_eye_openness(
    outer_point,
    inner_point,
    upper_point,
    lower_point
):
    """
    คำนวณ Eye Openness Ratio ของตาหนึ่งข้าง


    Horizontal Width:

        outer ●--------------● inner


    Vertical Opening:

                  ● upper
                  |
                  |
                  ● lower


    Formula:

        vertical_px
        -----------
        horizontal_px
    """

    # ======================================================
    # 1. Convert Point -> Pixel XY
    # ======================================================

    outer_xy = (
        _get_pixel_xy(
            outer_point
        )
    )


    inner_xy = (
        _get_pixel_xy(
            inner_point
        )
    )


    upper_xy = (
        _get_pixel_xy(
            upper_point
        )
    )


    lower_xy = (
        _get_pixel_xy(
            lower_point
        )
    )


    # ======================================================
    # 2. Validate
    # ======================================================

    if any(
        point is None
        for point in (
            outer_xy,
            inner_xy,
            upper_xy,
            lower_xy,
        )
    ):
        return None


    # ======================================================
    # 3. Horizontal Width
    # ======================================================

    horizontal_px = (
        _distance_2d(
            outer_xy,
            inner_xy
        )
    )


    # ======================================================
    # 4. Vertical Opening
    # ======================================================

    vertical_px = (
        _distance_2d(
            upper_xy,
            lower_xy
        )
    )


    if (
        horizontal_px is None
        or
        vertical_px is None
    ):
        return None


    # ======================================================
    # 5. Prevent Division by Zero
    # ======================================================

    if horizontal_px <= 1e-6:
        return None


    # ======================================================
    # 6. Eye Openness Ratio
    # ======================================================

    openness = (
        vertical_px
        /
        horizontal_px
    )


    if not _is_finite_number(
        openness
    ):
        return None


    if openness < 0:
        return None


    # ======================================================
    # 7. Return
    # ======================================================

    return {

        "horizontal_px": float(
            horizontal_px
        ),

        "vertical_px": float(
            vertical_px
        ),

        "openness": float(
            openness
        ),
    }


# ==========================================================
# Calculate Both Eyes
# ==========================================================

def calculate_eye_openness(
    face_points
):
    """
    คำนวณ Eye Openness Ratio ของตาทั้งสองข้าง


    Required RIGHT landmarks:

        right_eye_outer
        right_eye_inner
        right_eye_upper
        right_eye_lower


    Required LEFT landmarks:

        left_eye_outer
        left_eye_inner
        left_eye_upper
        left_eye_lower


    Returns:

    {
        "right_eye_openness": ...,
        "left_eye_openness": ...,
        "mean_eye_openness": ...,

        "right_eye": {
            "horizontal_px": ...,
            "vertical_px": ...,
            "openness": ...
        },

        "left_eye": {
            ...
        }
    }


    Expected:

        OPEN
        -> openness สูงกว่า

        CLOSED
        -> openness ลดลง

        OPEN again
        -> openness กลับสูงขึ้น


    IMPORTANT:

    Function นี้ยังไม่รู้ว่า
    ค่าเท่าไร = OPEN
    ค่าเท่าไร = CLOSED

    เรื่อง Threshold จะทำใน Eye State ภายหลัง
    """

    # ======================================================
    # 1. Validate Required Eye Points
    # ======================================================

    validation = (
        validate_eye_points(
            face_points
        )
    )


    if not validation[
        "valid"
    ]:
        return None


    # ======================================================
    # 2. RIGHT Eye
    # ======================================================

    right_eye = (
        _calculate_single_eye_openness(

            face_points[
                "right_eye_outer"
            ],

            face_points[
                "right_eye_inner"
            ],

            face_points[
                "right_eye_upper"
            ],

            face_points[
                "right_eye_lower"
            ],
        )
    )


    # ======================================================
    # 3. LEFT Eye
    # ======================================================

    left_eye = (
        _calculate_single_eye_openness(

            face_points[
                "left_eye_outer"
            ],

            face_points[
                "left_eye_inner"
            ],

            face_points[
                "left_eye_upper"
            ],

            face_points[
                "left_eye_lower"
            ],
        )
    )


    if (
        right_eye is None
        or
        left_eye is None
    ):
        return None


    # ======================================================
    # 4. Openness Each Eye
    # ======================================================

    right_eye_openness = float(
        right_eye[
            "openness"
        ]
    )


    left_eye_openness = float(
        left_eye[
            "openness"
        ]
    )


    # ======================================================
    # 5. Mean Both Eyes
    #
    # ใช้สำหรับดูภาพรวม/debug
    #
    # แต่ตอน Eye State
    # เราจะไม่ใช้ mean ตัวเดียวตัดสิน blink
    # ======================================================

    mean_eye_openness = (
        right_eye_openness
        +
        left_eye_openness
    ) / 2.0


    # ======================================================
    # 6. Final Result
    # ======================================================

    return {

        "right_eye_openness": (
            right_eye_openness
        ),

        "left_eye_openness": (
            left_eye_openness
        ),

        "mean_eye_openness": float(
            mean_eye_openness
        ),

        "right_eye": (
            right_eye
        ),

        "left_eye": (
            left_eye
        ),
    }