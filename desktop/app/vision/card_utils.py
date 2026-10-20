import cv2
import numpy as np


def is_rectangle(approx):
    """
    ตรวจว่า contour ที่ถูกประมาณแล้ว
    มีลักษณะใกล้เคียงสี่เหลี่ยมผืนผ้าหรือไม่
    """

    # ต้องมี 4 มุม
    if len(approx) != 4:
        return False

    # ต้องเป็น Convex
    if not cv2.isContourConvex(approx):
        return False

    points = approx.reshape(4, 2)

    for i in range(4):

        p1 = points[i - 1]
        p2 = points[i]
        p3 = points[(i + 1) % 4]

        v1 = p1 - p2
        v2 = p3 - p2

        dot = np.dot(v1, v2)

        len1 = np.linalg.norm(v1)
        len2 = np.linalg.norm(v2)

        if len1 == 0 or len2 == 0:
            return False

        cos_angle = abs(
            dot / (len1 * len2)
        )

        # 90° จะมี cos ใกล้ 0
        if cos_angle > 0.25:
            return False

    return True


def order_corners(points):
    """
    เรียงจุดเป็น
    Top-Left
    Top-Right
    Bottom-Right
    Bottom-Left
    """

    points = points.reshape(4, 2)

    ordered = np.zeros(
        (4, 2),
        dtype=np.float32
    )

    sums = points.sum(axis=1)

    diffs = (
        points[:, 0]
        - points[:, 1]
    )

    ordered[0] = points[
        np.argmin(sums)
    ]

    ordered[2] = points[
        np.argmax(sums)
    ]

    ordered[1] = points[
        np.argmax(diffs)
    ]

    ordered[3] = points[
        np.argmin(diffs)
    ]

    return ordered


def check_side_lengths(approx, tolerance=0.25):
    """
    ตรวจว่าด้านตรงข้ามมีความยาวใกล้เคียงกัน
    """

    points = order_corners(approx)

    tl, tr, br, bl = points

    top = np.linalg.norm(
        tr - tl
    )

    bottom = np.linalg.norm(
        br - bl
    )

    left = np.linalg.norm(
        bl - tl
    )

    right = np.linalg.norm(
        br - tr
    )

    if (
        top == 0
        or bottom == 0
        or left == 0
        or right == 0
    ):
        return False

    horizontal_diff = (
        abs(top - bottom)
        / max(top, bottom)
    )

    vertical_diff = (
        abs(left - right)
        / max(left, right)
    )

    if horizontal_diff > tolerance:
        return False

    if vertical_diff > tolerance:
        return False

    return True