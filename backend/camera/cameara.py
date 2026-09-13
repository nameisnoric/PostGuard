import cv2


def start_camera():
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        print("Error: Cannot open camera")
        return

    while True:
        ret, frame = cam.read()

        if not ret:
            print("Error: Cannot read frame")
            break

        frame = cv2.flip(frame,1) #กลับด้านซ้าย-ขวาของกล้อง
        cv2.imshow("PostGuard Camera", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    start_camera()