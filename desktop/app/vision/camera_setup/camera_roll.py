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

    # เส้นกลางภาพ (เด่นกว่า)
    cv2.line(img, (w // 2, 0), (w // 2, h), (0, 255, 255), 2)
    cv2.line(img, (0, h // 2), (w, h // 2), (0, 255, 255), 2)


def estimate_scene_tilt(frame):
    """
    หาเส้นตรงเกือบตั้ง/เกือบนอนในห้อง (เฉพาะพื้นที่กลางภาพ)
    แล้วคืนค่ามุมเอียงกลาง (องศา, บวก = เอียงตามเข็ม)
    ถ้าไม่เจอเส้นชัดเจนคืน None

    ใช้กับภาพดิบที่ยังไม่หมุน
    """
    h, w = frame.shape[:2]
    crop = frame[int(h * 0.2):int(h * 0.8), int(w * 0.2):int(w * 0.8)]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)

    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=60,
        minLineLength=crop.shape[0] // 4,
        maxLineGap=10
    )

    if lines is None:
        return None

    # แปลงให้เป็น (N, 4) เสมอ ไม่ว่า OpenCV จะส่งรูปแบบไหนมา
    lines = lines.reshape(-1, 4)

    angles = []
    for x1, y1, x2, y2 in lines:
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        angle = (angle + 45) % 90 - 45        # แปลงให้อยู่ใน -45..+45 (ตั้ง/นอนนับเหมือนกัน)
        if abs(angle) <= 15:                  # เอาเฉพาะเส้นที่เกือบตั้ง/นอน
            angles.append(angle)

    if len(angles) < 5:
        return None

    return float(np.median(angles))


def shoulder_tilt_report(left_shoulder, right_shoulder, threshold=3.0):
    """
    ใช้กับภาพที่ผ่าน level_frame แล้ว (ห้ามลบค่ากล้องเอียงซ้ำ)
    ยังไม่ตีความว่าไหล่เอียงจริง ให้ผู้ใช้ยืนยันก่อน
    """
    if left_shoulder[0] > right_shoulder[0]:
        left_shoulder, right_shoulder = right_shoulder, left_shoulder

    tilt = float(np.degrees(np.arctan2(right_shoulder[1] - left_shoulder[1],
                                       right_shoulder[0] - left_shoulder[0])))

    return {"tilt_deg": tilt, "needs_user_confirm": abs(tilt) > threshold}