import cv2

CARD_RATIO = 1.586


def get_guide_bounds(frame):
    """
    คำนวณตำแหน่งกรอบ Guide
    คืนค่า x1, y1, x2, y2
    """

    height, width = frame.shape[:2]

    guide_width = int(width * 0.35)
    guide_height = int(guide_width / CARD_RATIO)

    center_x = width // 2
    center_y = height // 2

    x1 = center_x - guide_width // 2
    y1 = center_y - guide_height // 2
    x2 = center_x + guide_width // 2
    y2 = center_y + guide_height // 2

    return x1, y1, x2, y2


def draw_guide(frame):
    """
    วาดกรอบ Guide ลงบนภาพสำหรับแสดงผล
    """

    x1, y1, x2, y2 = get_guide_bounds(frame)

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (0, 255, 255),
        2
    )

    cv2.putText(
        frame,
        "Place reference card here",
        (x1, y2 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )

    return frame