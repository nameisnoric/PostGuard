
import cv2

CAMERA_INDEX = 0

cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    raise RuntimeError("Cannot open webcam")

try:
    # ขอใช้ MJPEG เพื่อรองรับความละเอียดสูงบนเว็บแคมหลายรุ่น
    cap.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*"MJPG")
    )

    # ขอความละเอียด 1280x720 ที่ 30 FPS
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    success, frame = cap.read()

    if not success:
        raise RuntimeError("Cannot read frame")

    height, width = frame.shape[:2]

    print(f"Requested: 1280x720")
    print(f"Actual: {width}x{height}")
    print(f"FPS reported: {cap.get(cv2.CAP_PROP_FPS)}")

finally:
    cap.release()
