import cv2

from guide import get_guide_bounds, draw_guide
from card_detection import detect_rectangle
from card_validation import check_position, check_size
from card_perspective import (
    warp_card,
    calculate_pixel_scale
)
from camera_reference import (
    check_scale_consistency,
    create_camera_reference
)


def put(img, text, pos, color):
    """
    ฟังก์ชันช่วยแสดงข้อความบน Frame
    """

    cv2.putText(
        img,
        text,
        pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2
    )


def main():

    # =========================
    # เปิดกล้อง
    # =========================

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Can't open camera")
        return

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    window = "PostGuard - Camera Setup"

    cv2.namedWindow(
        window,
        cv2.WINDOW_NORMAL
    )

    # =========================
    # Stability Settings
    # =========================

    stable_count = 0

    STABLE_FRAMES = 10

    # =========================
    # Camera Reference State
    # =========================

    camera_reference = None
    system_state = SystemState.CAMERA_SETUP

    while True:

        # =========================
        # อ่าน Frame
        # =========================

        ret, frame = cap.read()

        if not ret:
            print("Error: Can't read frame")
            break

        # Mirror Webcam
        frame = cv2.flip(
            frame,
            1
        )

        # =========================
        # Guide
        # =========================

        bounds = get_guide_bounds(
            frame
        )

        # =========================
        # Rectangle Detection
        # =========================

        result, edges, debug = detect_rectangle(
            frame,
            bounds
        )

        # ภาพสำหรับ UI
        display = frame.copy()

        draw_guide(
            display,
            bounds
        )

        # reset ทุก Frame
        card_valid = False

        # =========================
        # CASE 1:
        # ไม่พบ Rectangle
        # =========================

        if result is None:

            stable_count = 0

            put(
                display,
                "Not found",
                (20, 40),
                (0, 0, 255)
            )

        # =========================
        # CASE 2:
        # พบ Rectangle
        # =========================

        else:

            # =========================
            # ไม่ใช่ Reference Card
            # =========================

            if not result["is_card"]:

                stable_count = 0

                color = (
                    255,
                    150,
                    0
                )

                cv2.drawContours(
                    display,
                    [result["box"]],
                    -1,
                    color,
                    3
                )

                put(
                    display,
                    "Rectangle found (not a card)",
                    (20, 40),
                    color
                )

                put(
                    display,
                    f"ratio={result['ratio']:.2f}  "
                    f"fill={result['fill']:.0%}  "
                    f"fit={result['fit']:.0%}",
                    (20, 75),
                    (255, 255, 255)
                )

            # =========================
            # Reference Card Candidate
            # =========================

            else:

                color = (
                    0,
                    255,
                    0
                )

                cv2.drawContours(
                    display,
                    [result["box"]],
                    -1,
                    color,
                    3
                )

                put(
                    display,
                    "Reference Card Candidate",
                    (20, 40),
                    color
                )

                put(
                    display,
                    f"ratio={result['ratio']:.2f}  "
                    f"fill={result['fill']:.0%}  "
                    f"fit={result['fit']:.0%}",
                    (20, 75),
                    (255, 255, 255)
                )

                # =========================
                # Position Validation
                # =========================

                position = check_position(
                    result["box"],
                    bounds
                )

                if position["valid"]:

                    put(
                        display,
                        "Position: OK",
                        (20, 110),
                        (0, 255, 0)
                    )

                else:

                    put(
                        display,
                        f"Position: "
                        f"{position['direction']}",
                        (20, 110),
                        (0, 255, 255)
                    )

                # =========================
                # Size Validation
                # =========================

                size = check_size(
                    result["fill"]
                )

                if size["valid"]:

                    put(
                        display,
                        "Card Size: OK",
                        (20, 145),
                        (0, 255, 0)
                    )

                else:

                    put(
                        display,
                        f"Card Size: "
                        f"{size['direction']}",
                        (20, 145),
                        (0, 255, 255)
                    )

                # =========================
                # Stability Validation
                # =========================

                if (
                    position["valid"]
                    and size["valid"]
                ):

                    stable_count += 1

                else:

                    stable_count = 0

                # ไม่ให้เกิน 10
                stable_count = min(
                    stable_count,
                    STABLE_FRAMES
                )

                if (
                    stable_count
                    >= STABLE_FRAMES
                ):

                    card_valid = True

                # =========================
                # Stability Status
                # =========================

                if not card_valid:

                    put(
                        display,
                        f"Stability: "
                        f"{stable_count}/"
                        f"{STABLE_FRAMES}",
                        (20, 180),
                        (0, 255, 255)
                    )

                # =========================
                # Card Valid
                # =========================

                else:

                    put(
                        display,
                        "Reference Card Valid",
                        (20, 180),
                        (0, 255, 0)
                    )

                    # =========================
                    # Perspective Transform
                    # =========================

                    perspective = warp_card(
                        frame,
                        result["box"]
                    )

                    if perspective is not None:

                        warped_card = (
                            perspective["image"]
                        )

                        width_px = (
                            perspective["width_px"]
                        )

                        height_px = (
                            perspective["height_px"]
                        )

                        # =========================
                        # Pixel Scale
                        # =========================

                        scale = calculate_pixel_scale(
                            width_px,
                            height_px
                        )

                        put(
                            display,
                            f"Scale X: "
                            f"{scale['x']:.2f} px/mm",
                            (20, 215),
                            (0, 255, 0)
                        )

                        put(
                            display,
                            f"Scale Y: "
                            f"{scale['y']:.2f} px/mm",
                            (20, 250),
                            (0, 255, 0)
                        )

                        put(
                            display,
                            f"Scale AVG: "
                            f"{scale['average']:.2f} px/mm",
                            (20, 285),
                            (0, 255, 0)
                        )

                        # =========================
                        # Scale Consistency
                        # =========================

                        scale_valid = (
                            check_scale_consistency(
                                scale
                            )
                        )

                        if scale_valid:

                            put(
                                display,
                                "Scale: OK",
                                (20, 320),
                                (0, 255, 0)
                            )

                            # =========================
                            # Create Camera Reference
                            # ทำครั้งเดียว
                            # =========================

                            if camera_reference is None:

                                camera_reference = (
                                    create_camera_reference(
                                        frame,
                                        result,
                                        perspective,
                                        scale
                                    )
                                )
                                system_state = SystemState.CAMERA_SETUP_COMPLETE
                                print(
                                    "Camera Reference Created"
                                )

                                print(
                                    camera_reference
                                )

                        else:

                            put(
                                display,
                                "Scale: NOT CONSISTENT",
                                (20, 320),
                                (0, 0, 255)
                            )

                        # =========================
                        # Warped Card Debug
                        # =========================

                        cv2.imshow(
                            "PostGuard - Warped Card",
                            warped_card
                        )

        # =========================
        # Camera Setup Complete
        # =========================

        if camera_reference is not None:

            put(
                display,
                "Camera Setup: COMPLETE",
                (20, 355),
                (0, 255, 0)
            )

        # =========================
        # Debug Information
        # =========================

        put(
            display,
            f"Contours: "
            f"{debug['contours']}",
            (20, 405),
            (255, 255, 255)
        )

        put(
            display,
            f"Size: "
            f"{debug['passed_size']}  "
            f"4-corner: "
            f"{debug['passed_4_corners']}  "
            f"Fit: "
            f"{debug['passed_fit']}  "
            f"Inside: "
            f"{debug['passed_inside']}",
            (20, 440),
            (255, 255, 255)
        )

        # =========================
        # Display Main Window
        # =========================

        cv2.imshow(
            window,
            display
        )

        # Edge Debug
        cv2.imshow(
            "PostGuard - Edge Debug",
            edges
        )

        # =========================
        # Keyboard
        # =========================

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("q"):
            break

    # =========================
    # Cleanup
    # =========================

    cap.release()

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()