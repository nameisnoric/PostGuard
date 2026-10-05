import cv2

CARD_RATIO = 1.586   # บัตรมาตรฐาน 85.6 x 53.98 mm


def get_guide_bounds(frame, width_ratio=0.35):
    """กรอบ Guide กลางภาพ สัดส่วนเท่าบัตร"""
    h, w = frame.shape[:2]
    gw = int(w * width_ratio)
    gh = int(gw / CARD_RATIO)
    cx, cy = w // 2, h // 2
    return cx - gw // 2, cy - gh // 2, cx + gw // 2, cy + gh // 2


def draw_guide(frame, bounds):
    x1, y1, x2, y2 = bounds
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)