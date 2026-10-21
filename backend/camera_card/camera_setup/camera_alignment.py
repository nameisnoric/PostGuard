import numpy as np


def calculate_card_roll(box):
    """
    คำนวณมุมเอียงของ Reference Card
    จากขอบบนและขอบล่าง

    box เรียงเป็น:
    TL, TR, BR, BL
    """

    tl, tr, br, bl = box

    top_angle = np.degrees(
        np.arctan2(
            tr[1] - tl[1],
            tr[0] - tl[0]
        )
    )

    bottom_angle = np.degrees(
        np.arctan2(
            br[1] - bl[1],
            br[0] - bl[0]
        )
    )

    roll = (
        top_angle + bottom_angle
    ) / 2

    return float(roll)


def calculate_guide_roll(bounds):
    """
    Guide ปัจจุบันเป็นกรอบแนวนอน
    ดังนั้นมุมอ้างอิงคือ 0 องศา
    """

    return 0.0


def calculate_roll_error(
    box,
    bounds
):
    """
    คำนวณว่า Card เบี่ยงจากแนว Guide
    กี่องศา
    """

    card_roll = calculate_card_roll(
        box
    )

    guide_roll = calculate_guide_roll(
        bounds
    )

    roll_error = (
        card_roll - guide_roll
    )

    return float(
        roll_error
    )


def calculate_perspective(box):
    """
    วัดความแตกต่างของด้าน Card
    เพื่อใช้เป็น Perspective Quality Indicator

    box:
    TL, TR, BR, BL
    """

    tl, tr, br, bl = box

    # ความกว้างด้านบน
    width_top = np.linalg.norm(
        tr - tl
    )

    # ความกว้างด้านล่าง
    width_bottom = np.linalg.norm(
        br - bl
    )

    # ความสูงด้านซ้าย
    height_left = np.linalg.norm(
        bl - tl
    )

    # ความสูงด้านขวา
    height_right = np.linalg.norm(
        br - tr
    )

    # ซ้าย-ขวาต่างกันเท่าไร
    horizontal_perspective = (
        abs(height_left - height_right)
        / max(
            height_left,
            height_right,
            1e-6
        )
    )

    # บน-ล่างต่างกันเท่าไร
    vertical_perspective = (
        abs(width_top - width_bottom)
        / max(
            width_top,
            width_bottom,
            1e-6
        )
    )

    return {
        "horizontal": float(
            horizontal_perspective
        ),
        "vertical": float(
            vertical_perspective
        )
    }


def check_alignment(
    box,
    bounds,
    max_roll=5.0,
    max_horizontal_perspective=0.10,
    max_vertical_perspective=0.10
):
    """
    ตรวจสอบ Alignment ของ Reference Card

    ตรวจ 3 อย่าง:
    1. Roll Error
    2. Horizontal Perspective
    3. Vertical Perspective

    Threshold ตอนนี้เป็นค่า Prototype
    """

    # =========================
    # Roll
    # =========================

    roll_error = calculate_roll_error(
        box,
        bounds
    )

    roll_valid = (
        abs(roll_error)
        <= max_roll
    )

    # =========================
    # Perspective
    # =========================

    perspective = calculate_perspective(
        box
    )

    horizontal_valid = (
        perspective["horizontal"]
        <= max_horizontal_perspective
    )

    vertical_valid = (
        perspective["vertical"]
        <= max_vertical_perspective
    )

    # =========================
    # Final Result
    # =========================

    valid = (
        roll_valid
        and horizontal_valid
        and vertical_valid
    )

    return {
        "valid": valid,

        "roll_error": roll_error,

        "horizontal_perspective":
            perspective["horizontal"],

        "vertical_perspective":
            perspective["vertical"],

        "roll_valid":
            roll_valid,

        "horizontal_valid":
            horizontal_valid,

        "vertical_valid":
            vertical_valid
    }