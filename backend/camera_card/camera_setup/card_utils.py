import cv2
import numpy as np


def order_corners(points):

    points = np.asarray(points, dtype=np.float32).reshape(4, 2)

    ordered = np.zeros((4, 2), dtype=np.float32)

    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]

    ordered[0] = points[np.argmin(sums)]
    ordered[1] = points[np.argmax(diffs)]
    ordered[2] = points[np.argmax(sums)]
    ordered[3] = points[np.argmin(diffs)]

    return ordered


def get_rotated_rectangle(contour):

    rect = cv2.minAreaRect(contour)

    (center_x, center_y), (width, height), angle = rect

    if width <= 0 or height <= 0:
        return None

    box = cv2.boxPoints(rect)

    box = order_corners(box)

    return {
        "rect": rect,
        "box": box,
        "center": (center_x, center_y),
        "width": width,
        "height": height,
        "angle": angle
    }


def get_aspect_ratio(width, height):

    if width <= 0 or height <= 0:
        return 0

    return max(width, height) / min(width, height)


def calculate_rectangularity(contour, width, height):

    rectangle_area = width * height

    if rectangle_area <= 0:
        return 0

    contour_area = cv2.contourArea(contour)

    return contour_area / rectangle_area