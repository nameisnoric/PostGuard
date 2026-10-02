import cv2

from guide import draw_guide
from card_detection import detect_card


def main():

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print(
            "Error: Can't open camera"
        )
        return

    print(
        "Camera open success"
    )

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    window_name = (
        "PostGuard - Camera Setup"
    )

    cv2.namedWindow(
        window_name,
        cv2.WINDOW_NORMAL
    )

    while True:

        ret, frame = cap.read()

        if not ret:
            print(
                "Error: Can't read frame"
            )
            break

        # Mirror
        frame = cv2.flip(
            frame,
            1
        )

        # ----------------------
        # Detection
        # ใช้ภาพก่อนวาด UI
        # ----------------------

        card = detect_card(
            frame
        )

        # ----------------------
        # Display
        # ----------------------

        display_frame = frame.copy()

        draw_guide(
            display_frame
        )

        # ----------------------
        # ถ้าเจอ Card
        # ----------------------

        if card is not None:

            cv2.drawContours(
                display_frame,
                [card],
                -1,
                (0, 255, 0),
                3
            )

            cv2.putText(
                display_frame,
                "Reference Card Detected",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                display_frame,
                "Reference Card Not Found",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        cv2.imshow(
            window_name,
            display_frame
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("q"):
            break

    cap.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()