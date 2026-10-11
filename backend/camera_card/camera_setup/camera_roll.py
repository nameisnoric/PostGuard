import cv2
import numpy as np


def level_frame(frame, roll_deg, remove_black_border=True):
    """
    หมุนภาพเพื่อแก้ Camera Roll

    remove_black_border=True
    จะ Zoom ภาพเล็กน้อยเพื่อไม่ให้เกิดขอบดำ
    """
    h, w = frame.shape[:2]

    if remove_black_border:
        angle_rad = np.radians(abs(roll_deg))

        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        scale_x = cos_a + (h / w) * sin_a
        scale_y = cos_a + (w / h) * sin_a

        scale = max(scale_x, scale_y)
    else:
        scale = 1.0

    matrix = cv2.getRotationMatrix2D(
        (w / 2, h / 2),
        roll_deg,
        scale
    )

    corrected = cv2.warpAffine(
        frame,
        matrix,
        (w, h)
    )

    return corrected


def draw_level_grid(img, step=160):
    """วาดเส้นตารางตั้ง/นอน ให้ผู้ใช้เทียบกับขอบประตูหรือผนัง"""
    h, w = img.shape[:2]

    for x in range(step, w, step):
        cv2.line(img, (x, 0), (x, h), (255, 255, 255), 1)

    for y in range(step, h, step):
        cv2.line(img, (0, y), (w, y), (255, 255, 255), 1)

    cv2.line(img, (w // 2, 0), (w // 2, h), (0, 255, 255), 2)
    cv2.line(img, (0, h // 2), (w, h // 2), (0, 255, 255), 2)


def _normalize_axis_angle(angle_deg):
    """
    แปลงมุมของเส้นให้เป็นความเอียงเทียบกับแกนแนวนอน/แนวตั้งที่ใกล้ที่สุด
    ผลลัพธ์อยู่ในช่วง -45 ถึง +45 องศา
    """
    return (float(angle_deg) + 45.0) % 90.0 - 45.0


def _weighted_median(values, weights):
    """หา Median แบบให้น้ำหนักด้วยความยาวของเส้น"""
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)

    if values.size == 0 or weights.size != values.size:
        return None

    total_weight = float(np.sum(weights))

    if total_weight <= 0:
        return None

    order = np.argsort(values)
    values = values[order]
    weights = weights[order]

    cumulative = np.cumsum(weights)
    cutoff = total_weight * 0.5

    index = int(np.searchsorted(cumulative, cutoff, side="left"))
    index = min(index, len(values) - 1)

    return float(values[index])


def estimate_scene_tilt(frame):
    """
    ประมาณ Camera Roll จากเส้นโครงสร้างในฉาก

    ขั้นตอน:
    1. ใช้ ROI กว้างกว่าเวอร์ชันเดิม
    2. เพิ่ม local contrast เพื่อช่วยฉากที่ contrast ต่ำ
    3. ตรวจเส้นด้วย HoughLinesP
    4. รวมแนวตั้ง/แนวนอนให้อยู่ใน axis-relative angle เดียวกัน
    5. ให้น้ำหนักตามความยาวของเส้น
    6. หา dominant angle cluster ก่อน
    7. ใช้ weighted median ของ cluster หลัก

    คืนค่า:
        float -> มุมฉากโดยประมาณ
        None  -> ข้อมูลเส้นไม่พอหรือไม่น่าเชื่อถือ
    """

    if frame is None:
        return None

    h, w = frame.shape[:2]

    if h < 40 or w < 40:
        return None

    # ใช้พื้นที่ภาพมากขึ้นเพื่อไม่ตัดขอบประตู/ผนังออกมากเกินไป
    crop = frame[
        int(h * 0.08):int(h * 0.92),
        int(w * 0.08):int(w * 0.92)
    ]

    if crop.size == 0:
        return None

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    # ช่วยเพิ่ม contrast ของเส้นในฉาก
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        blurred,
        40,
        120
    )

    min_dimension = min(crop.shape[:2])

    min_line_length = max(
        40,
        int(min_dimension * 0.12)
    )

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 360.0,
        threshold=35,
        minLineLength=min_line_length,
        maxLineGap=25
    )

    if lines is None:
        return None

    lines = lines.reshape(-1, 4)

    angles = []
    weights = []

    for x1, y1, x2, y2 in lines:
        dx = float(x2 - x1)
        dy = float(y2 - y1)

        length = float(np.hypot(dx, dy))

        if length < min_line_length:
            continue

        raw_angle = float(
            np.degrees(
                np.arctan2(dy, dx)
            )
        )

        axis_angle = _normalize_axis_angle(
            raw_angle
        )

        # เปิดช่วงเผื่อ noise มากกว่าเวอร์ชันเดิม
        if abs(axis_angle) > 20.0:
            continue

        angles.append(axis_angle)
        weights.append(length)

    if len(angles) < 3:
        return None

    angles = np.asarray(
        angles,
        dtype=np.float64
    )

    weights = np.asarray(
        weights,
        dtype=np.float64
    )

    # หา dominant orientation ด้วย histogram แบบถ่วงน้ำหนัก
    bin_edges = np.arange(
        -20.5,
        21.5,
        1.0
    )

    histogram, histogram_edges = np.histogram(
        angles,
        bins=bin_edges,
        weights=weights
    )

    if histogram.size == 0:
        return None

    peak_index = int(
        np.argmax(histogram)
    )

    peak_center = (
        histogram_edges[peak_index]
        +
        histogram_edges[peak_index + 1]
    ) / 2.0

    # ใช้เฉพาะเส้นที่อยู่ใกล้ dominant orientation
    cluster_mask = (
        np.abs(
            angles - peak_center
        )
        <= 3.0
    )

    cluster_angles = angles[cluster_mask]
    cluster_weights = weights[cluster_mask]

    if len(cluster_angles) < 2:
        return None

    total_weight = float(
        np.sum(weights)
    )

    cluster_weight = float(
        np.sum(cluster_weights)
    )

    if total_weight <= 0:
        return None

    confidence = (
        cluster_weight
        /
        total_weight
    )

    # ถ้า dominant cluster อ่อนเกินไป ไม่เดามุมมั่ว
    if confidence < 0.20:
        return None

    result = _weighted_median(
        cluster_angles,
        cluster_weights
    )

    if result is None:
        return None

    return float(result)


def shoulder_tilt_report(
    left_shoulder,
    right_shoulder,
    threshold=3.0
):
    """
    ใช้กับภาพที่ผ่าน level_frame แล้ว
    ห้ามลบค่ากล้องเอียงซ้ำ
    """

    if left_shoulder[0] > right_shoulder[0]:
        left_shoulder, right_shoulder = (
            right_shoulder,
            left_shoulder
        )

    tilt = float(
        np.degrees(
            np.arctan2(
                right_shoulder[1] - left_shoulder[1],
                right_shoulder[0] - left_shoulder[0]
            )
        )
    )

    return {
        "tilt_deg": tilt,
        "needs_user_confirm": abs(tilt) > threshold
    }
