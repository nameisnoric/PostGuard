import numpy as np


def get_card_center(box):
    """
    หาจุดกึ่งกลางของกรอบการ์ด
    box มี 4 มุม
    """
    center_x = np.mean(box[:, 0])
    center_y = np.mean(box[:, 1])

    return center_x, center_y


def check_position(box, bounds, tolerance=0.08):
    """
    ตรวจว่าการ์ดอยู่ใกล้กึ่งกลาง Guide หรือไม่

    tolerance = 0.08
    หมายถึงยอมให้คลาดประมาณ 8% ของขนาด Guide
    """

    x1, y1, x2, y2 = bounds

    guide_width = x2 - x1
    guide_height = y2 - y1

    guide_center_x = (x1 + x2) / 2
    guide_center_y = (y1 + y2) / 2

    card_center_x, card_center_y = get_card_center(box)

    dx = card_center_x - guide_center_x
    dy = card_center_y - guide_center_y

    tolerance_x = guide_width * tolerance
    tolerance_y = guide_height * tolerance

    # อยู่ในตำแหน่งเหมาะสม
    if abs(dx) <= tolerance_x and abs(dy) <= tolerance_y:
        return {
            "valid": True,
            "direction": "OK"
        }

    # เลือกแกนที่คลาดมากกว่า
    if abs(dx) > abs(dy):
        if dx < 0:
            direction = "MOVE RIGHT"
        else:
            direction = "MOVE LEFT"

    else:
        if dy < 0:
            direction = "MOVE DOWN"
        else:
            direction = "MOVE UP"

    return {
        "valid": False,
        "direction": direction
    }

def check_size(fill, min_fill=0.35, max_fill=0.75):
    """
    ตรวจขนาดของ Reference Card เทียบกับ Guide

    fill ต่ำเกินไป = Card เล็ก / อยู่ไกล
    fill สูงเกินไป = Card ใหญ่ / อยู่ใกล้
    """

    if fill < min_fill:
        return {
            "valid": False,
            "direction": "MOVE CLOSER"
        }

    if fill > max_fill:
        return {
            "valid": False,
            "direction": "MOVE FARTHER"
        }

    return {
        "valid": True,
        "direction": "OK"
    }