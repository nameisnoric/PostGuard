import cv2
import numpy as np

from camera_setup.guide import CARD_RATIO

CANNY_LOW = 30
CANNY_HIGH = 90

MIN_FILL = 0.20
MIN_FIT = 0.75

RATIO_TOLERANCE = 0.05  


def order_corners(pts):
    """เรียงมุม: บนซ้าย, บนขวา, ล่างขวา, ล่างซ้าย"""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = pts[:, 0] - pts[:, 1]
    return np.array([pts[np.argmin(s)], pts[np.argmax(d)],
                     pts[np.argmax(s)], pts[np.argmin(d)]], dtype=np.float32)

def check_rectangle_angles(box, min_angle=65, max_angle=115):
    """
    ตรวจว่ามุมทั้ง 4 ของรูปใกล้เคียงมุมฉาก
    ยอมให้คลาดจาก 90 องศาได้พอสมควร
    เพื่อรองรับ Perspective
    """

    for i in range(4):
        prev_point = box[(i - 1) % 4]
        current_point = box[i]
        next_point = box[(i + 1) % 4]

        v1 = prev_point - current_point
        v2 = next_point - current_point

        len1 = np.linalg.norm(v1)
        len2 = np.linalg.norm(v2)

        if len1 == 0 or len2 == 0:
            return False

        cosine = np.dot(v1, v2) / (len1 * len2)

        cosine = np.clip(
            cosine,
            -1.0,
            1.0
        )

        angle = np.degrees(
            np.arccos(cosine)
        )

        if angle < min_angle or angle > max_angle:
            return False

    return True

def get_ratio(box):
    """อัตราส่วนด้านยาว / ด้านสั้น"""
    tl, tr, br, bl = box
    w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    return max(w, h) / max(min(w, h), 1e-6)


def detect_rectangle(frame, bounds):
    """
    หาสี่เหลี่ยมในกรอบ Guide

    คืนค่า:
    result = None หรือข้อมูล rectangle
    edges = ภาพ edge สำหรับ debug
    debug = ข้อมูลว่า contour ผ่านแต่ละขั้นกี่อัน
    """

    x1, y1, x2, y2 = bounds
    gw, gh = x2 - x1, y2 - y1
    guide_area = gw * gh

    # -------------------------
    # 1. Crop ROI
    # -------------------------
    pad_x = int(gw * 0.15)
    pad_y = int(gh * 0.15)

    fh, fw = frame.shape[:2]

    rx1 = max(0, x1 - pad_x)
    ry1 = max(0, y1 - pad_y)
    rx2 = min(fw, x2 + pad_x)
    ry2 = min(fh, y2 + pad_y)

    roi = frame[ry1:ry2, rx1:rx2]

    # -------------------------
    # 2. Edge Detection
    # -------------------------
    gray = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2GRAY
    )

    blur = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        blur,
        CANNY_LOW,
        CANNY_HIGH
    )

    kernel = np.ones(
        (3, 3),
        np.uint8
    )

    edges = cv2.dilate(
        edges,
        kernel,
        iterations=1
    )

    # -------------------------
    # 3. Contours
    # -------------------------
    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # debug counters
    debug = {
        "contours": len(contours),
        "passed_size": 0,
        "passed_4_corners": 0,
        "passed_angles": 0,
        "passed_fit": 0,
        "passed_inside": 0,
    }

    offset = np.array(
        [rx1, ry1],
        dtype=np.float32
    )

    best = None
    best_area = 0

    for contour in contours:

        # -------------------------
        # 4. Size
        # -------------------------
        hull = cv2.convexHull(
            contour
        )

        hull_area = cv2.contourArea(
            hull
        )

        if hull_area < MIN_FILL * guide_area:
            continue

        debug["passed_size"] += 1

        # -------------------------
        # 5. 4 corners
        # -------------------------
        peri = cv2.arcLength(
            hull,
            True
        )

        approx = cv2.approxPolyDP(
            hull,
            0.03 * peri,
            True
        )

        if len(approx) != 4:
            continue

        debug["passed_4_corners"] += 1

        box = (
            order_corners(approx)
            + offset
        )
        if not check_rectangle_angles(box):
            continue

        debug["passed_angles"] += 1
        # -------------------------
        # 6. Fit
        # -------------------------
        quad_area = cv2.contourArea(
            box
        )

        if quad_area <= 0:
            continue

        fit = (
            min(hull_area, quad_area)
            / max(hull_area, quad_area)
        )

        if fit < MIN_FIT:
            continue

        debug["passed_fit"] += 1

        # -------------------------
        # 7. Inside Guide
        # -------------------------
        mx = gw * 0.05
        my = gh * 0.05

        inside = np.all(
            (box[:, 0] >= x1 - mx)
            & (box[:, 0] <= x2 + mx)
            & (box[:, 1] >= y1 - my)
            & (box[:, 1] <= y2 + my)
        )

        if not inside:
            continue

        debug["passed_inside"] += 1

        # -------------------------
        # 8. Best candidate
        # -------------------------
        if quad_area > best_area:

            best_area = quad_area

            best = {
                "box": box,
                "fill": quad_area / guide_area,
                "fit": fit
            }

    # -------------------------
    # ไม่พบ Rectangle
    # -------------------------
    if best is None:
        return None, edges, debug

    # -------------------------
    # 9. Ratio
    # -------------------------
    ratio = get_ratio(
        best["box"]
    )

    is_card = (
        abs(ratio - CARD_RATIO)
        / CARD_RATIO
        <= RATIO_TOLERANCE
    )

    result = {
        "box": best["box"].astype(np.int32),
        "ratio": ratio,
        "fill": best["fill"],
        "fit": best["fit"],
        "is_card": is_card
    }

    return result, edges, debug