import cv2
import numpy as np


CARD_WIDTH_MM = 85.60
CARD_HEIGHT_MM = 53.98


def order_corners(points):
    """
    เรียง 4 มุม:
    TL, TR, BR, BL
    """

    points = np.asarray(
        points,
        dtype=np.float32
    ).reshape(4, 2)

    ordered = np.zeros(
        (4, 2),
        dtype=np.float32
    )

    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]

    ordered[0] = points[np.argmin(sums)]   # TL
    ordered[1] = points[np.argmax(diffs)]  # TR
    ordered[2] = points[np.argmax(sums)]   # BR
    ordered[3] = points[np.argmin(diffs)]  # BL

    return ordered


def warp_card(frame, box):
    """
    แปลง Perspective ของ Card
    ให้กลายเป็นภาพสี่เหลี่ยมตรง
    """

    box = order_corners(box)

    tl, tr, br, bl = box

    # ความกว้างด้านบน / ล่าง
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)

    # ความสูงด้านซ้าย / ขวา
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)

    width_px = int(
        max(width_top, width_bottom)
    )

    height_px = int(
        max(height_left, height_right)
    )

    if width_px <= 0 or height_px <= 0:
        return None

    destination = np.array(
        [
            [0, 0],
            [width_px - 1, 0],
            [width_px - 1, height_px - 1],
            [0, height_px - 1]
        ],
        dtype=np.float32
    )

    matrix = cv2.getPerspectiveTransform(
        box,
        destination
    )

    warped = cv2.warpPerspective(
        frame,
        matrix,
        (width_px, height_px)
    )

    return {
        "image": warped,
        "width_px": width_px,
        "height_px": height_px,
        "matrix": matrix
    }


def calculate_pixel_scale(width_px, height_px):
    """
    คำนวณ pixel ต่อ millimeter
    """

    px_per_mm_x = (
        width_px / CARD_WIDTH_MM
    )

    px_per_mm_y = (
        height_px / CARD_HEIGHT_MM
    )

    px_per_mm = (
        px_per_mm_x + px_per_mm_y
    ) / 2

    return {
        "x": px_per_mm_x,
        "y": px_per_mm_y,
        "average": px_per_mm
    }