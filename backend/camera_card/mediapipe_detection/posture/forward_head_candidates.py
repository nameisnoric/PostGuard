import math


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่าค่าเป็น finite number

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - invalid type
    """

    if value is None:
        return False

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
# Get XY
# ==========================================================

def _get_xy(point):
    """
    ดึงตำแหน่ง x/y ของ Landmark

    Face Point:
    พยายามใช้ x_float/y_float ก่อน
    เพราะมี sub-pixel precision

    Pose Point:
    ปัจจุบันใช้ x/y
    """

    if point is None:
        return None

    try:

        if (
            "x_float" in point
            and
            "y_float" in point
        ):

            x = float(
                point["x_float"]
            )

            y = float(
                point["y_float"]
            )

        else:

            x = float(
                point["x"]
            )

            y = float(
                point["y"]
            )

    except (
        KeyError,
        TypeError,
        ValueError,
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
# 2D Distance
# ==========================================================

def _distance_2d(
    point_a,
    point_b,
):
    """
    Euclidean distance ในภาพ
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
        dx ** 2
        +
        dy ** 2
    )


    if (
        not _is_finite_number(
            distance
        )
        or
        distance <= 1e-6
    ):

        return None


    return float(
        distance
    )


# ==========================================================
# Midpoint
# ==========================================================

def _midpoint(
    point_a,
    point_b,
):

    if (
        point_a is None
        or
        point_b is None
    ):

        return None


    return (
        (
            point_a[0]
            +
            point_b[0]
        )
        / 2.0,

        (
            point_a[1]
            +
            point_b[1]
        )
        / 2.0,
    )


# ==========================================================
# Calculate Forward Head Candidates
# ==========================================================

def calculate_forward_head_candidates(
    pose_points,
    face_points,
):
    """
    Forward Head Candidate Metrics สำหรับ Front Camera


    --------------------------------------------------------
    Candidate A:
    Eye / Shoulder Scale Ratio
    --------------------------------------------------------

        eye_shoulder_ratio
            =
        inter_eye_distance_px
        ---------------------
        shoulder_width_px


    แนวคิด:

    ถ้าศีรษะยื่นเข้าใกล้กล้อง
    แต่ไหล่ยังอยู่ตำแหน่งเดิม:

        Face scale ↑
        Shoulder scale ≈ เดิม

        Ratio ↑


    ถ้าโน้มทั้งตัว:

        Face scale ↑
        Shoulder scale ↑

        Ratio ควรเปลี่ยนน้อยกว่า


    --------------------------------------------------------
    Candidate B:
    Face / Shoulder Scale Ratio
    --------------------------------------------------------

        face_shoulder_ratio
            =
        face_width_px
        -----------------
        shoulder_width_px


    ใช้ landmark:

        right_face = 234
        left_face  = 454


    --------------------------------------------------------
    IMPORTANT
    --------------------------------------------------------

    ทั้งสองค่าเป็น:

        Prototype Frontal-View Proxy

    ไม่ใช่:
    - Craniovertebral Angle
    - Physical head displacement
    - Clinical FHP measurement
    - RULA score
    - Risk threshold

    ต้องผ่าน Validation ก่อนใช้จริง
    """


    # ======================================================
    # 1. Input Check
    # ==========================================================

    if (
        pose_points is None
        or
        face_points is None
    ):

        return None


    # ======================================================
    # 2. Pose Shoulder Points
    # ==========================================================

    try:

        left_shoulder_raw = (
            pose_points[
                "left_shoulder"
            ]
        )

        right_shoulder_raw = (
            pose_points[
                "right_shoulder"
            ]
        )

    except (
        KeyError,
        TypeError,
    ):

        return None


    left_shoulder = _get_xy(
        left_shoulder_raw
    )

    right_shoulder = _get_xy(
        right_shoulder_raw
    )


    if (
        left_shoulder is None
        or
        right_shoulder is None
    ):

        return None


    # ======================================================
    # 3. Shoulder Width
    # ==========================================================

    shoulder_width_px = (
        _distance_2d(
            left_shoulder,
            right_shoulder,
        )
    )


    if shoulder_width_px is None:

        return None


    # ======================================================
    # 4. Eye Points
    # ==========================================================

    required_eye_points = (
        "left_eye_outer",
        "left_eye_inner",
        "right_eye_inner",
        "right_eye_outer",
    )


    for name in required_eye_points:

        if name not in face_points:

            return None


    left_eye_outer = _get_xy(
        face_points[
            "left_eye_outer"
        ]
    )

    left_eye_inner = _get_xy(
        face_points[
            "left_eye_inner"
        ]
    )

    right_eye_inner = _get_xy(
        face_points[
            "right_eye_inner"
        ]
    )

    right_eye_outer = _get_xy(
        face_points[
            "right_eye_outer"
        ]
    )


    if any(
        point is None
        for point in (
            left_eye_outer,
            left_eye_inner,
            right_eye_inner,
            right_eye_outer,
        )
    ):

        return None


    # ======================================================
    # 5. Eye Centers
    # ==========================================================

    left_eye_center = (
        _midpoint(
            left_eye_outer,
            left_eye_inner,
        )
    )

    right_eye_center = (
        _midpoint(
            right_eye_inner,
            right_eye_outer,
        )
    )


    inter_eye_distance_px = (
        _distance_2d(
            left_eye_center,
            right_eye_center,
        )
    )


    if inter_eye_distance_px is None:

        return None


    # ======================================================
    # 6. Face Width
    # ==========================================================

    try:

        right_face = _get_xy(
            face_points[
                "right_face"
            ]
        )

        left_face = _get_xy(
            face_points[
                "left_face"
            ]
        )

    except (
        KeyError,
        TypeError,
    ):

        return None


    face_width_px = (
        _distance_2d(
            right_face,
            left_face,
        )
    )


    if face_width_px is None:

        return None


    # ======================================================
    # 7. Candidate A
    #
    # Eye scale relative to Shoulder scale
    # ==========================================================

    eye_shoulder_ratio = (
        inter_eye_distance_px
        /
        shoulder_width_px
    )


    # ======================================================
    # 8. Candidate B
    #
    # Whole face scale relative to Shoulder scale
    # ==========================================================

    face_shoulder_ratio = (
        face_width_px
        /
        shoulder_width_px
    )


    # ======================================================
    # 9. Validate
    # ==========================================================

    if not all(
        _is_finite_number(value)
        for value in (
            eye_shoulder_ratio,
            face_shoulder_ratio,
            shoulder_width_px,
            inter_eye_distance_px,
            face_width_px,
        )
    ):

        return None


    # ======================================================
    # 10. Return
    # ==========================================================

    return {

        # --------------------------------------------------
        # Candidate Metrics
        # --------------------------------------------------

        "eye_shoulder_ratio": float(
            eye_shoulder_ratio
        ),

        "face_shoulder_ratio": float(
            face_shoulder_ratio
        ),


        # --------------------------------------------------
        # Raw Measurements
        # --------------------------------------------------

        "shoulder_width_px": float(
            shoulder_width_px
        ),

        "inter_eye_distance_px": float(
            inter_eye_distance_px
        ),

        "face_width_px": float(
            face_width_px
        ),
    }