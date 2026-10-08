import cv2

CARD_RATIO = 1.586

def draw_guide(frame):
    """
    วาดกรอบสำหรับให้ผู้ใช้วาง Reference Card
    โดยอิงจากขนาดของ Frame จริง
    """

    height, width = frame.shape[:2]

    # กำหนดให้ Guide กว้าง 35% ของภาพ
    guide_width = int(width * 0.35)

    # คำนวณความสูงตามสัดส่วนของ Card
    guide_height = int(guide_width / CARD_RATIO)

    # จุดกึ่งกลางของภาพ
    center_x = width // 2
    center_y = height // 2

    # มุมของ Guide
    x1 = center_x - guide_width // 2
    y1 = center_y - guide_height // 2
    x2 = center_x + guide_width // 2
    y2 = center_y + guide_height // 2

    # วาดกรอบ
    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (0, 255, 255),
        2
    )

    # ข้อความแนะนำ
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

def detect_card(frame):
    height, width = frame.shape[:2]

    guide_width = int(width * 0.35)
    guide_height = int(guide_width / 1.586)

    center_x = width // 2
    center_y = height // 2

    x1 = center_x - guide_width // 2
    y1 = center_y - guide_height // 2
    x2 = center_x + guide_width // 2
    y2 = center_y + guide_height // 2

    # Crop เฉพาะพื้นที่ Guide
    roi = frame[y1:y2, x1:x2]

    # แปลงเป็นภาพเทา
    gray = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2GRAY
    )

    # ลด Noise
    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    # หา Edge
    edges = cv2.Canny(
        blurred,
        50,
        150
    )

    # หา Contour
    contours, _ = cv2.findContours(
        edges,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for contour in contours:

        area = cv2.contourArea(contour)

        # ตัดวัตถุเล็กเกินไป
        if area < 3000:
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

        # ต้องมี 4 มุม
        if not is_rectangle(approx):
            continue

        x, y, w, h = cv2.boundingRect(
            approx
        )

        if h == 0:
            continue

        ratio = w / h

        if ratio < 1:
            ratio = h / w

        # ตรวจสัดส่วน Card
        if abs(ratio - 1.586) > 0.25:
            continue

        # แปลงตำแหน่งจาก ROI กลับเป็น Frame หลัก
        approx[:, 0, 0] += x1
        approx[:, 0, 1] += y1

        return approx

    return None

def is_rectangle(approx):
    # ต้องมี 4 มุม
    if len(approx) != 4:
        return False

    # ต้องเป็นรูปนูน
    if not cv2.isContourConvex(approx):
        return False

    # ตรวจมุม
    points = approx.reshape(4, 2)

    for i in range(4):
        p1 = points[i - 1]
        p2 = points[i]
        p3 = points[(i + 1) % 4]

        v1 = p1 - p2
        v2 = p3 - p2

        dot = v1[0] * v2[0] + v1[1] * v2[1]

        len1 = (v1[0]**2 + v1[1]**2) ** 0.5
        len2 = (v2[0]**2 + v2[1]**2) ** 0.5

        if len1 == 0 or len2 == 0:
            return False

        cos_angle = abs(dot / (len1 * len2))

        # 90° -> cos ใกล้ 0
        if cos_angle > 0.25:
            return False

    return True

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Can't open camera")
        return
    print("Camera open success")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    window_name = "PosrGaurd - Camera-Setup"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(
        window_name,
        cv2.WINDOW_FULLSCREEN,
        cv2.WND_PROP_FULLSCREEN
    )

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Error: Cant read frame")
            break
        print(frame.shape)

        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
                
        card = detect_card(frame)
        frame = draw_guide(frame)
        
        if card is not None:

            cv2.drawContours(
                frame,
                [card],
                -1,
                (0, 255, 0),
                3
            )

            cv2.putText(
                frame,
                "Reference Card Detected",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
  
if __name__ == "__main__":
    main()
