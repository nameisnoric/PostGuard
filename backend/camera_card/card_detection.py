import cv2

from guide import (
    CARD_RATIO,
    get_guide_bounds
)

from card_utils import (
    is_rectangle,
    check_side_lengths
)


def detect_card(frame):
    """
    ตรวจหา Reference Card
    ภายในพื้นที่ Guide
    """

    x1, y1, x2, y2 = get_guide_bounds(
        frame
    )

    roi = frame[
        y1:y2,
        x1:x2
    ]

    # ----------------------
    # Preprocessing
    # ----------------------

    gray = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2GRAY
    )

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        blurred,
        50,
        150
    )

    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    roi_height, roi_width = roi.shape[:2]

    guide_area = (
        roi_width
        * roi_height
    )

    candidates = []

    # ----------------------
    # ตรวจแต่ละ Contour
    # ----------------------

    for contour in contours:

        area = cv2.contourArea(
            contour
        )

        if guide_area == 0:
            continue

        area_ratio = (
            area / guide_area
        )

        # Card ต้องมีขนาดเหมาะสม
        if area_ratio < 0.30:
            continue

        if area_ratio > 1.05:
            continue

        perimeter = cv2.arcLength(
            contour,
            True
        )

        approx = cv2.approxPolyDP(
            contour,
            0.02 * perimeter,
            True
        )

        # ----------------------
        # Shape validation
        # ----------------------

        if not is_rectangle(approx):
            continue

        if not check_side_lengths(
            approx
        ):
            continue

        x, y, w, h = cv2.boundingRect(
            approx
        )

        if w == 0 or h == 0:
            continue

        # ----------------------
        # Aspect Ratio
        # ----------------------

        ratio = w / h

        if ratio < 1:
            ratio = 1 / ratio

        ratio_error = abs(
            ratio - CARD_RATIO
        )

        if ratio_error > 0.25:
            continue

        # ----------------------
        # Rectangularity
        # ----------------------

        bounding_area = w * h

        if bounding_area == 0:
            continue

        rectangularity = (
            area / bounding_area
        )

        if rectangularity < 0.80:
            continue

        # ----------------------
        # Candidate Score
        # ----------------------

        score = (
            rectangularity
            - ratio_error
        )

        candidates.append(
            (score, approx)
        )

    # ----------------------
    # ไม่เจอ Card
    # ----------------------

    if not candidates:
        return None

    # ----------------------
    # เลือก Candidate ที่ดีที่สุด
    # ----------------------

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_card = (
        candidates[0][1]
    )

    # แปลงจาก ROI coordinate
    # กลับเป็น Full Frame
    best_card[:, 0, 0] += x1
    best_card[:, 0, 1] += y1

    return best_card