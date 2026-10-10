import math


# ==========================================================
# Numeric Helper
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่าค่าเป็นตัวเลขปกติหรือไม่

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - String ที่ไม่สามารถแปลงเป็นตัวเลข
    """

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
# Candidate Prototype Metric:
# Torso Orientation
# ==========================================================

def calculate_torso_orientation(
    pose_points_or_left_shoulder,
    right_shoulder=None,
):
    """
    Candidate Prototype Metric:
    Torso Orientation / Torso Yaw Proxy


    =========================================================
    PURPOSE
    =========================================================

    ประมาณการหมุนลำตัวจากไหล่ซ้ายและไหล่ขวา

    ใช้เฉพาะ:

        left_shoulder
        right_shoulder

    ไม่ใช้:

        hip
        waist
        nose
        ear
        head yaw


    =========================================================
    INPUT COMPATIBILITY
    =========================================================

    รองรับทั้งแบบเก่าของ DetectionPipeline:

        calculate_torso_orientation(
            pose_points
        )

    และแบบเรียกตรง:

        calculate_torso_orientation(
            left_shoulder,
            right_shoulder
        )


    =========================================================
    FORMULA
    =========================================================

    Shoulder vector:

        dx =
            right_shoulder.world_x
            -
            left_shoulder.world_x


        dz =
            right_shoulder.world_z
            -
            left_shoulder.world_z


    Torso angle:

        atan2(
            dz,
            abs(dx)
        )


    เมื่อหันหน้าตรง:

        shoulder depth difference
        ควรอยู่ใกล้ 0


    เมื่อหมุนลำตัว:

        shoulder depth difference
        จะเพิ่มขึ้นในทิศใดทิศหนึ่ง


    =========================================================
    IMPORTANT
    =========================================================

    นี่เป็น Torso Rotation Proxy

    ไม่ใช่:
    - Clinical torso rotation angle
    - Risk threshold
    - RULA score

    ต้องผ่าน Torso Cross-talk Test ก่อน
    เปลี่ยน status เป็น validated_prototype
    """


    # ======================================================
    # 1. Resolve Input
    # ======================================================

    if right_shoulder is None:

        pose_points = (
            pose_points_or_left_shoulder
        )


        if not isinstance(
            pose_points,
            dict,
        ):

            return None


        left_shoulder = (
            pose_points.get(
                "left_shoulder"
            )
        )


        right_shoulder = (
            pose_points.get(
                "right_shoulder"
            )
        )


    else:

        left_shoulder = (
            pose_points_or_left_shoulder
        )


    # ======================================================
    # 2. Validate Landmarks
    # ======================================================

    if (
        left_shoulder is None
        or right_shoulder is None
    ):

        return None


    # ======================================================
    # 3. Read Pose World Coordinates
    # ======================================================

    try:

        left_x = float(
            left_shoulder[
                "world_x"
            ]
        )

        left_y = float(
            left_shoulder[
                "world_y"
            ]
        )

        left_z = float(
            left_shoulder[
                "world_z"
            ]
        )


        right_x = float(
            right_shoulder[
                "world_x"
            ]
        )

        right_y = float(
            right_shoulder[
                "world_y"
            ]
        )

        right_z = float(
            right_shoulder[
                "world_z"
            ]
        )


    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return None


    # ======================================================
    # 4. Validate Numeric Values
    # ======================================================

    values = (
        left_x,
        left_y,
        left_z,
        right_x,
        right_y,
        right_z,
    )


    if not all(
        _is_finite_number(value)
        for value in values
    ):

        return None


    # ======================================================
    # 5. Shoulder Vector
    # ======================================================

    world_dx = (
        right_x
        -
        left_x
    )


    world_dy = (
        right_y
        -
        left_y
    )


    world_dz = (
        right_z
        -
        left_z
    )


    # ======================================================
    # 6. Shoulder Width
    #
    # 3D width เก็บไว้เป็น Diagnostic
    # ======================================================

    width_3d = math.sqrt(
        world_dx ** 2
        +
        world_dy ** 2
        +
        world_dz ** 2
    )


    if width_3d <= 1e-6:

        return None


    # ======================================================
    # 7. Shoulder Width in XZ Plane
    #
    # ใช้สำหรับการหมุนรอบแกนตั้ง
    # ======================================================

    width_xz = math.hypot(
        world_dx,
        world_dz,
    )


    if width_xz <= 1e-6:

        return None


    # ======================================================
    # 8. Torso Orientation Angle
    #
    # abs(dx)
    #
    # ทำให้ denominator เป็น magnitude
    # ส่วน sign ของ orientation
    # มาจาก depth difference dz
    # ======================================================

    angle = math.degrees(
        math.atan2(
            world_dz,
            abs(
                world_dx
            ),
        )
    )


    if not _is_finite_number(
        angle
    ):

        return None


    # ======================================================
    # 9. Depth Ratio
    #
    # Diagnostic metric
    # ======================================================

    depth_ratio = (
        world_dz
        /
        width_xz
    )


    # ======================================================
    # 10. Return
    #
    # IMPORTANT:
    #
    # คืน key เก่าที่ DetectionPipeline ใช้อยู่:
    #
    # angle
    # world_dx
    # world_dz
    # width_3d
    #
    # และเพิ่ม key ใหม่สำหรับ debug/test
    # ======================================================

    return {

        # ----------------------------------------------
        # Main Metric
        # ----------------------------------------------

        "angle": float(
            angle
        ),

        "torso_angle": float(
            angle
        ),


        # ----------------------------------------------
        # Shoulder Vector
        # ----------------------------------------------

        "world_dx": float(
            world_dx
        ),

        "world_dy": float(
            world_dy
        ),

        "world_dz": float(
            world_dz
        ),


        # ----------------------------------------------
        # Width
        # ----------------------------------------------

        "width_3d": float(
            width_3d
        ),

        "width_xz": float(
            width_xz
        ),


        # ----------------------------------------------
        # Diagnostics
        # ----------------------------------------------

        "shoulder_depth_difference": float(
            world_dz
        ),

        "depth_ratio": float(
            depth_ratio
        ),


        # ----------------------------------------------
        # Development Status
        # ----------------------------------------------

        "status": (
            "candidate_prototype"
        ),
    }