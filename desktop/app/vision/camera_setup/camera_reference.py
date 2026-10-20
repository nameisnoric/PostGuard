def check_scale_consistency(scale, tolerance=0.05):
    """
    ตรวจว่า Scale X และ Y ต่างกันไม่เกิน tolerance

    tolerance = 0.05
    หมายถึงยอมให้ต่างกันไม่เกิน 5%
    """

    scale_x = scale["x"]
    scale_y = scale["y"]

    average = (scale_x + scale_y) / 2

    if average <= 0:
        return False

    difference = abs(
        scale_x - scale_y
    ) / average

    return difference <= tolerance


def create_camera_reference(
    frame,
    result,
    perspective,
    scale
):
    """
    สร้างข้อมูล Camera Reference
    สำหรับใช้ต่อใน Session
    """

    height, width = frame.shape[:2]

    return {
        "status": "VALID",

        # Resolution ของกล้องตอน Setup
        "frame_width": width,
        "frame_height": height,

        # มุมของ Reference Card
        "card_box": result["box"].copy(),

        # ขนาด Card ที่ตรวจได้ใน Pixel
        "card_width_px": perspective["width_px"],
        "card_height_px": perspective["height_px"],

        # Camera Reference Scale
        "scale_x": scale["x"],
        "scale_y": scale["y"],
        "scale_avg": scale["average"],

        # Transformation
        "perspective_matrix": perspective["matrix"]
    }