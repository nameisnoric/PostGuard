import math


# ==========================================================
# Helper
# ==========================================================

def _is_finite_number(value):
    """
    ตรวจว่าค่าที่รับเข้ามาเป็นตัวเลขปกติหรือไม่

    ป้องกัน:
    - None
    - NaN
    - Infinity
    - String ที่แปลงเป็นตัวเลขไม่ได้
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
# Validated Prototype Metric: Shoulder Tilt
# ==========================================================

def calculate_shoulder_tilt(
    left_shoulder,
    right_shoulder
):
    """
    Validated Prototype Metric: Shoulder Tilt

    ใช้แนวเส้นระหว่าง:
        Left Shoulder
        Right Shoulder

    Convention จาก validation:

        Left Shoulder High
        -> Negative

        Right Shoulder High
        -> Positive

    ยังไม่ใช่:
    - Risk threshold
    - RULA score
    - Clinical measurement
    """

    # ======================================================
    # 1. ตรวจ Landmark
    # ======================================================

    if (
        left_shoulder is None
        or right_shoulder is None
    ):
        return None


    # ======================================================
    # 2. Difference X / Y
    # ======================================================

    try:

        dx = (
            right_shoulder["x"]
            -
            left_shoulder["x"]
        )

        dy = (
            right_shoulder["y"]
            -
            left_shoulder["y"]
        )

    except (
        KeyError,
        TypeError
    ):
        return None


    # ======================================================
    # 3. Validate numeric values
    # ======================================================

    if (
        not _is_finite_number(dx)
        or
        not _is_finite_number(dy)
    ):
        return None


    # จุดเดียวกันไม่สามารถสร้างเส้นได้
    if dx == 0 and dy == 0:
        return None


    # ======================================================
    # 4. Calculate Shoulder Line Angle
    # ======================================================

    angle = math.degrees(
        math.atan2(
            dy,
            dx
        )
    )


    # ======================================================
    # 5. Normalize
    #
    # ทำให้แนวนอนอยู่ใกล้ 0°
    #
    # Result:
    # -90 ... +90
    # ======================================================

    if angle > 90:
        angle -= 180

    elif angle < -90:
        angle += 180


    return float(
        angle
    )


# ==========================================================
# Validated Prototype Metric: Shoulder Elevation
# ==========================================================

def calculate_shoulder_elevation(
    nose,
    left_shoulder,
    right_shoulder,
):
    """
    Candidate Prototype Metric:
    Shoulder Elevation v2

    IMPORTANT
    ---------
    nose ถูกเก็บไว้ใน parameter
    เพื่อให้ DetectionPipeline เดิมยังเรียก function นี้ได้

    แต่สูตรใหม่นี้จะไม่ใช้ nose

    เหตุผล:
    สูตรเดิมใช้:

        shoulder_y - nose_y

    ทำให้ตอน Neck Flexion
    nose เคลื่อนลงมาก
    และเกิด Cross-talk กับ Shoulder Elevation

    สูตรใหม่ใช้เฉพาะ Shoulder Landmark

        left_metric
            = left_shoulder_y
              / shoulder_width

        right_metric
            = right_shoulder_y
              / shoulder_width

    Convention:

        Shoulder moves upward
        -> image Y decreases
        -> metric decreases

    Metric นี้ออกแบบให้ใช้ร่วมกับ
    Personal Baseline

    ห้ามใช้ absolute value เป็น Risk Threshold
    ข้ามผู้ใช้หรือข้ามตำแหน่งกล้อง
    """

    # ======================================================
    # 1. Compatibility
    #
    # nose ยังรับเข้ามาเพื่อไม่ให้ Pipeline เดิมพัง
    # แต่ไม่ใช้ในการคำนวณ
    # ======================================================

    _ = nose


    # ======================================================
    # 2. Validate Landmarks
    # ======================================================

    if (
        left_shoulder is None
        or right_shoulder is None
    ):
        return None


    # ======================================================
    # 3. Read Coordinates
    # ======================================================

    try:

        left_x = float(
            left_shoulder["x"]
        )

        left_y = float(
            left_shoulder["y"]
        )

        right_x = float(
            right_shoulder["x"]
        )

        right_y = float(
            right_shoulder["y"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return None


    # ======================================================
    # 4. Validate Numbers
    # ======================================================

    values = (
        left_x,
        left_y,
        right_x,
        right_y,
    )


    if not all(
        _is_finite_number(value)
        for value in values
    ):
        return None


    # ======================================================
    # 5. Shoulder Width
    # ======================================================

    shoulder_dx = (
        right_x
        - left_x
    )

    shoulder_dy = (
        right_y
        - left_y
    )


    shoulder_width = math.sqrt(
        shoulder_dx ** 2
        +
        shoulder_dy ** 2
    )


    if shoulder_width <= 1e-6:
        return None


    # ======================================================
    # 6. Shoulder-only Elevation Metric
    # ======================================================

    left_metric = (
        left_y
        /
        shoulder_width
    )


    right_metric = (
        right_y
        /
        shoulder_width
    )


    # ======================================================
    # 7. Return
    # ======================================================

    return {

        "left": float(
            left_metric
        ),

        "right": float(
            right_metric
        ),

        "shoulder_width": float(
            shoulder_width
        ),

        "status": (
            "candidate_prototype"
        ),
    }


# ==========================================================
# Helper: Line Angle
# ==========================================================

def calculate_line_angle(
    point_a,
    point_b
):
    """
    คำนวณมุมของเส้นระหว่าง Landmark 2 จุด

    Normalize ให้อยู่ประมาณ:

        -90 ถึง +90 องศา

    ใช้เป็น helper สำหรับ Neck Lateral Tilt
    """

    # ======================================================
    # 1. ตรวจ Landmark
    # ======================================================

    if (
        point_a is None
        or point_b is None
    ):
        return None


    # ======================================================
    # 2. Difference X / Y
    # ======================================================

    try:

        dx = (
            point_b["x"]
            -
            point_a["x"]
        )

        dy = (
            point_b["y"]
            -
            point_a["y"]
        )

    except (
        KeyError,
        TypeError
    ):
        return None


    # ======================================================
    # 3. Validate
    # ======================================================

    if (
        not _is_finite_number(dx)
        or
        not _is_finite_number(dy)
    ):
        return None


    if dx == 0 and dy == 0:
        return None


    # ======================================================
    # 4. Calculate Angle
    # ======================================================

    angle = math.degrees(
        math.atan2(
            dy,
            dx
        )
    )


    # ======================================================
    # 5. Normalize
    # ======================================================

    if angle > 90:
        angle -= 180

    elif angle < -90:
        angle += 180


    return float(
        angle
    )


# ==========================================================
# Validated Prototype Metric: Neck Lateral Tilt
# ==========================================================

def calculate_neck_lateral_tilt(
    left_ear,
    right_ear,
    left_shoulder,
    right_shoulder
):
    """
    Validated Prototype Metric:
    Neck Lateral Tilt

    Formula:

        Ear Line Angle
        -
        Shoulder Line Angle

    ทำให้วัดการเอียงคอแบบ relative
    ต่อแนวไหล่

    ช่วยลดผลจากกรณี:
        ผู้ใช้เอียงทั้งลำตัว

    ผ่าน Prototype Validation แล้ว

    ยังไม่ใช่:
    - Risk threshold
    - RULA score
    - Clinical measurement
    """

    # ======================================================
    # 1. Ear Line Angle
    # ======================================================

    ear_angle = calculate_line_angle(
        left_ear,
        right_ear
    )


    # ======================================================
    # 2. Shoulder Line Angle
    # ======================================================

    shoulder_angle = calculate_line_angle(
        left_shoulder,
        right_shoulder
    )


    # ======================================================
    # 3. Validate
    # ======================================================

    if (
        ear_angle is None
        or shoulder_angle is None
    ):
        return None


    # ======================================================
    # 4. Relative Neck Lateral Tilt
    # ======================================================

    neck_tilt = (
        ear_angle
        -
        shoulder_angle
    )


    # ======================================================
    # 5. Normalize
    # ======================================================

    if neck_tilt > 90:
        neck_tilt -= 180

    elif neck_tilt < -90:
        neck_tilt += 180


    # ======================================================
    # 6. Return
    # ======================================================

    return {

        "ear_angle": float(
            ear_angle
        ),

        "shoulder_angle": float(
            shoulder_angle
        ),

        "neck_tilt": float(
            neck_tilt
        ),
    }


# ==========================================================
# Candidate Prototype Metric: Forward Head
# ==========================================================

def calculate_forward_head(
    nose,
    left_shoulder,
    right_shoulder
):
    """
    Candidate Prototype Metric: Forward Head

    ใช้ Pose World Landmarks

    แนวคิด:

        Forward Head
        = ตำแหน่งศีรษะในแกนความลึก
          เมื่อเทียบกับลำตัว / ไหล่

    Formula:

        shoulder_mid_z
            = (
                left_shoulder.world_z
                +
                right_shoulder.world_z
              ) / 2

        shoulder_width
            = 3D Distance ระหว่าง
              Left Shoulder
              และ Right Shoulder

        forward_head
            = (
                shoulder_mid_z
                -
                nose.world_z
              )
              / shoulder_width

    IMPORTANT:

    numerator ใช้ World Z

    ดังนั้น denominator ต้องใช้
    World XYZ Shoulder Width เช่นกัน

    ห้ามเอา Pixel Shoulder Width
    มาหาร World Z

    ตอนนี้ยังอยู่ในขั้น Validation

    ยังไม่ใช่:
    - Validated Prototype Metric
    - Risk threshold
    - RULA score
    - Alert
    - Personal Baseline
    """

    # ======================================================
    # 1. ตรวจ Landmark
    # ======================================================

    if (
        nose is None
        or left_shoulder is None
        or right_shoulder is None
    ):
        return None


    # ======================================================
    # 2. อ่าน Pose World Landmark
    # ======================================================

    try:

        nose_x = float(
            nose["world_x"]
        )

        nose_y = float(
            nose["world_y"]
        )

        nose_z = float(
            nose["world_z"]
        )


        left_x = float(
            left_shoulder["world_x"]
        )

        left_y = float(
            left_shoulder["world_y"]
        )

        left_z = float(
            left_shoulder["world_z"]
        )


        right_x = float(
            right_shoulder["world_x"]
        )

        right_y = float(
            right_shoulder["world_y"]
        )

        right_z = float(
            right_shoulder["world_z"]
        )

    except (
        KeyError,
        TypeError,
        ValueError
    ):
        return None


    # ======================================================
    # 3. Validate numeric values
    # ======================================================

    values = (
        nose_x,
        nose_y,
        nose_z,
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
    # 4. Shoulder Midpoint Z
    #
    # ใช้ depth เฉลี่ยของไหล่ซ้ายและขวา
    # เป็นตัวแทนตำแหน่ง depth ของลำตัว
    # ======================================================

    shoulder_mid_z = (
        left_z
        +
        right_z
    ) / 2.0


    # ======================================================
    # 5. Shoulder Width แบบ World XYZ
    # ======================================================

    shoulder_dx = (
        right_x
        -
        left_x
    )


    shoulder_dy = (
        right_y
        -
        left_y
    )


    shoulder_dz = (
        right_z
        -
        left_z
    )


    shoulder_width = math.sqrt(
        shoulder_dx ** 2
        +
        shoulder_dy ** 2
        +
        shoulder_dz ** 2
    )


    # ======================================================
    # 6. Protect divide by zero
    # ======================================================

    if shoulder_width <= 1e-6:
        return None


    # ======================================================
    # 7. Normalized Forward Head
    #
    # ยังไม่กำหนดว่า:
    #
    # + = Forward
    #
    # หรือ
    #
    # - = Forward
    #
    # ให้ validation เป็นตัวบอก
    # ======================================================

    forward_head = (
        shoulder_mid_z
        -
        nose_z
    ) / shoulder_width


    # ======================================================
    # 8. Return
    #
    # forward_head
    # = metric หลัก
    #
    # ค่าอื่นใช้ diagnostic/debug
    # ======================================================

    return {

        "forward_head": float(
            forward_head
        ),

        "nose_z": float(
            nose_z
        ),

        "shoulder_mid_z": float(
            shoulder_mid_z
        ),

        "shoulder_width": float(
            shoulder_width
        ),

        "left_shoulder_z": float(
            left_z
        ),

        "right_shoulder_z": float(
            right_z
        ),
    }