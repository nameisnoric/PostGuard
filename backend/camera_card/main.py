from collections import deque
from pathlib import Path

import cv2
import numpy as np

from system_state import SystemState

from camera_setup.guide import get_guide_bounds, draw_guide
from camera_setup.card_detection import detect_rectangle
from camera_setup.card_validation import check_position, check_size
from camera_setup.card_perspective import (
    warp_card,
    calculate_pixel_scale,
)
from camera_setup.camera_reference import (
    check_scale_consistency,
    create_camera_reference,
)
from camera_setup.camera_alignment import check_alignment
from camera_setup.camera_roll import (
    level_frame,
    draw_level_grid,
    estimate_scene_tilt,
)

from mediapipe_detection.pose.pose_detector import PoseDetector


# ==========================================================
# PATH
# ==========================================================
# อ้างอิง path จากตำแหน่ง main.py
#
# backend/
# └── camera_card/
#     ├── main.py
#     └── models/
#         └── pose_landmarker_lite.task
#
# ทำให้ไม่ว่าจะสั่ง run จาก directory ไหน
# โปรแกรมก็ยังหา model เจอ
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

POSE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "pose_landmarker_lite.task"
)


# ==========================================================
# CONFIG
# ==========================================================

# ต้องผ่านต่อเนื่องกี่ Frame
# ถึงจะถือว่าการ์ดนิ่ง
STABLE_FRAMES = 15


# ==========================================================
# COLOR
# OpenCV ใช้ BGR
# ==========================================================

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
BLUE = (255, 150, 0)


# ==========================================================
# TILT CONFIG
# ==========================================================

TILT_WINDOW = "Tilt Adjust"

# ตรงกลาง = ไม่หมุนภาพ
SLIDER_CENTER = 60

# slider 0-120
# ใช้ปรับประมาณ +30 ถึง -30 องศา
SLIDER_MAX = 120


# ==========================================================
# TEXT HELPER
# ==========================================================

def put(
    img,
    text,
    pos,
    color,
):
    """
    แสดงข้อความลงบน Frame
    """

    cv2.putText(
        img,
        text,
        pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
    )


# ==========================================================
# TRACKBAR CALLBACK
# ==========================================================

def nothing(_):
    """
    OpenCV Trackbar ต้องการ callback function
    แต่เราไม่ได้ต้องการทำอะไรทันทีตอน slider เปลี่ยน
    """
    pass


# ==========================================================
# OPEN TILT WINDOW
# ==========================================================

def open_tilt_window():
    """
    เปิดหน้าต่าง slider
    สำหรับปรับ Camera Roll
    """

    cv2.namedWindow(
        TILT_WINDOW,
        cv2.WINDOW_NORMAL,
    )

    cv2.resizeWindow(
        TILT_WINDOW,
        520,
        80,
    )

    cv2.createTrackbar(
        "Tilt",
        TILT_WINDOW,
        SLIDER_CENTER,
        SLIDER_MAX,
        nothing,
    )


# ==========================================================
# CLOSE TILT WINDOW
# ==========================================================

def close_tilt_window():
    """
    ปิดหน้าต่าง Tilt

    try/except ป้องกันกรณี Window ถูกปิดไปแล้ว
    """

    try:

        cv2.destroyWindow(
            TILT_WINDOW
        )

    except cv2.error:

        pass


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ======================================================
    # 1. ตรวจสอบ Pose Model
    # ======================================================
    #
    # เช็กก่อนสร้าง PoseDetector
    # เพื่อให้ Error อ่านง่าย
    # ======================================================

    if not POSE_MODEL_PATH.exists():

        print(
            "Error: Pose model not found"
        )

        print(
            "Expected path:"
        )

        print(
            POSE_MODEL_PATH
        )

        return


    print(
        "Pose model found:"
    )

    print(
        POSE_MODEL_PATH
    )


    # ======================================================
    # 2. เปิดกล้อง
    # ======================================================

    cap = cv2.VideoCapture(0)


    # ======================================================
    # ตรวจสอบว่ากล้องเปิดได้หรือไม่
    # ======================================================

    if not cap.isOpened():

        print(
            "Error: Can't open camera"
        )

        return


    # ======================================================
    # ตั้ง Resolution
    # ======================================================

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280,
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720,
    )


    # ======================================================
    # Main Window
    # ======================================================

    window = (
        "PostGuard - Camera Setup"
    )

    cv2.namedWindow(
        window,
        cv2.WINDOW_NORMAL,
    )


    # ======================================================
    # 3. ตัวแปรของระบบ
    # ======================================================

    # จำนวน Frame ที่ Card ผ่านเงื่อนไขต่อเนื่อง
    stable_count = 0


    # ข้อมูลอ้างอิงของกล้อง
    camera_reference = None


    # State เริ่มต้น
    system_state = (
        SystemState.CAMERA_SETUP
    )


    # ใช้บอกว่า Debug Window ถูกปิดแล้วหรือยัง
    debug_windows_closed = False


    # ======================================================
    # Camera Roll
    # ======================================================

    # ค่าแก้ความเอียงที่ผู้ใช้ปรับ
    adjust_roll = 0.0


    # เก็บค่าความเอียงย้อนหลัง 15 Frame
    #
    # ใช้ Median ลด Noise
    tilt_history = deque(
        maxlen=15
    )


    # ค่ากลางของ Scene Tilt
    #
    # None = ยังหาไม่ได้
    scene_roll = None


    # ======================================================
    # 4. สร้าง Pose Detector
    # ======================================================
    #
    # จุดสำคัญที่แก้จากโค้ดเดิม:
    #
    # เดิม:
    # model_path="models/pose_landmarker_lite.task"
    #
    # ใหม่:
    # ใช้ Absolute Path จาก main.py
    # ======================================================

    pose_detector = PoseDetector(
        model_path=str(
            POSE_MODEL_PATH
        )
    )


    print(
        "PoseDetector ready"
    )


    # ======================================================
    # 5. MAIN LOOP
    # ======================================================

    while True:

        # ==================================================
        # อ่าน Frame จาก Webcam
        # ==================================================

        ret, frame = cap.read()


        if not ret:

            print(
                "Error: Can't read frame"
            )

            break


        # ==================================================
        # Mirror Webcam
        # ==================================================
        #
        # ทำให้ภาพเหมือนกระจก
        # ==================================================

        frame = cv2.flip(
            frame,
            1,
        )


        # ==================================================
        # หลัง Camera Setup เสร็จ
        #
        # หากเข้าสู่ Personal Baseline
        # ให้หมุนภาพชดเชย Camera Roll ก่อน
        # ==================================================

        if (
            camera_reference
            is not None

            and

            system_state
            == SystemState.PERSONAL_BASELINE
        ):

            frame = level_frame(
                frame,
                camera_reference[
                    "camera_roll_deg"
                ],
            )


        # Frame สำหรับวาด UI
        display = frame.copy()


        # ==================================================
        # STATE 1
        # CAMERA SETUP
        # ==================================================

        if (
            system_state
            == SystemState.CAMERA_SETUP
        ):

            debug_windows_closed = False


            # ==============================================
            # กำหนด Guide Area
            # ==============================================

            bounds = get_guide_bounds(
                frame
            )


            # ==============================================
            # ตรวจจับ Reference Card
            # ==============================================

            (
                result,
                edges,
                debug,
            ) = detect_rectangle(
                frame,
                bounds,
            )


            # ==============================================
            # วาดกรอบ Guide
            # ==============================================

            draw_guide(
                display,
                bounds,
            )


            card_valid = False


            # ==============================================
            # ไม่พบ Rectangle
            # ==============================================

            if result is None:

                stable_count = 0

                put(
                    display,
                    "Not found",
                    (20, 40),
                    RED,
                )


            # ==============================================
            # พบ Rectangle
            # แต่ไม่ผ่านเงื่อนไข Card
            # ==============================================

            elif not result[
                "is_card"
            ]:

                stable_count = 0


                cv2.drawContours(
                    display,
                    [
                        result[
                            "box"
                        ]
                    ],
                    -1,
                    BLUE,
                    3,
                )


                put(
                    display,
                    (
                        "Rectangle found "
                        "(not a card)"
                    ),
                    (20, 40),
                    BLUE,
                )


                put(
                    display,
                    (
                        f"ratio="
                        f"{result['ratio']:.2f} "

                        f"fill="
                        f"{result['fill']:.0%} "

                        f"fit="
                        f"{result['fit']:.0%}"
                    ),
                    (20, 75),
                    WHITE,
                )


            # ==============================================
            # พบ Reference Card Candidate
            # ==============================================

            else:

                cv2.drawContours(
                    display,
                    [
                        result[
                            "box"
                        ]
                    ],
                    -1,
                    GREEN,
                    3,
                )


                put(
                    display,
                    "Reference Card Candidate",
                    (20, 40),
                    GREEN,
                )


                put(
                    display,
                    (
                        f"ratio="
                        f"{result['ratio']:.2f} "

                        f"fill="
                        f"{result['fill']:.0%} "

                        f"fit="
                        f"{result['fit']:.0%}"
                    ),
                    (20, 75),
                    WHITE,
                )


                # ==========================================
                # POSITION
                # ==========================================

                position = check_position(
                    result[
                        "box"
                    ],
                    bounds,
                )


                if position[
                    "valid"
                ]:

                    put(
                        display,
                        "Position: OK",
                        (20, 110),
                        GREEN,
                    )

                else:

                    put(
                        display,
                        (
                            "Position: "
                            f"{position['direction']}"
                        ),
                        (20, 110),
                        YELLOW,
                    )


                # ==========================================
                # SIZE
                # ==========================================

                size = check_size(
                    result[
                        "fill"
                    ]
                )


                if size[
                    "valid"
                ]:

                    put(
                        display,
                        "Card Size: OK",
                        (20, 145),
                        GREEN,
                    )

                else:

                    put(
                        display,
                        (
                            "Card Size: "
                            f"{size['direction']}"
                        ),
                        (20, 145),
                        YELLOW,
                    )


                # ==========================================
                # ALIGNMENT
                # ==========================================
                #
                # max_roll=45
                #
                # ไม่ Reject การ์ดเพราะ Roll
                # เพราะ Roll จะไปแก้ในขั้นถัดไป
                #
                # จุดนี้เน้น Perspective
                # ==========================================

                alignment = check_alignment(
                    result[
                        "box"
                    ],
                    bounds,
                    max_roll=45.0,
                )


                put(
                    display,
                    (
                        "Card tilt: "
                        f"{alignment['roll_error']:.2f} "
                        "deg"
                    ),
                    (20, 215),
                    WHITE,
                )


                put(
                    display,
                    (
                        "H-Perspective: "
                        f"{alignment['horizontal_perspective']:.1%}"
                    ),
                    (20, 250),
                    WHITE,
                )


                put(
                    display,
                    (
                        "V-Perspective: "
                        f"{alignment['vertical_perspective']:.1%}"
                    ),
                    (20, 285),
                    WHITE,
                )


                # ==========================================
                # STABILITY
                # ==========================================
                #
                # Card ต้อง:
                #
                # Position ผ่าน
                # Size ผ่าน
                # Alignment ผ่าน
                #
                # ติดต่อกัน 15 Frame
                # ==========================================

                if (
                    position[
                        "valid"
                    ]

                    and

                    size[
                        "valid"
                    ]

                    and

                    alignment[
                        "valid"
                    ]
                ):

                    stable_count += 1

                else:

                    stable_count = 0


                stable_count = min(
                    stable_count,
                    STABLE_FRAMES,
                )


                if (
                    stable_count
                    >= STABLE_FRAMES
                ):

                    card_valid = True


                # ==========================================
                # Card ยังไม่นิ่ง
                # ==========================================

                if not card_valid:

                    put(
                        display,
                        (
                            "Stability: "
                            f"{stable_count}/"
                            f"{STABLE_FRAMES}"
                        ),
                        (20, 320),
                        YELLOW,
                    )


                # ==========================================
                # CARD VALID
                # ==========================================

                else:

                    put(
                        display,
                        "Reference Card Valid",
                        (20, 180),
                        GREEN,
                    )


                    # ======================================
                    # Warp Card
                    # ======================================

                    perspective = warp_card(
                        frame,
                        result[
                            "box"
                        ],
                    )


                    if (
                        perspective
                        is not None
                    ):

                        # ==============================
                        # PIXEL SCALE
                        # ==============================

                        scale = (
                            calculate_pixel_scale(
                                perspective[
                                    "width_px"
                                ],
                                perspective[
                                    "height_px"
                                ],
                            )
                        )


                        put(
                            display,
                            (
                                "Scale X: "
                                f"{scale['x']:.2f} "
                                "px/mm"
                            ),
                            (700, 40),
                            GREEN,
                        )


                        put(
                            display,
                            (
                                "Scale Y: "
                                f"{scale['y']:.2f} "
                                "px/mm"
                            ),
                            (700, 75),
                            GREEN,
                        )


                        put(
                            display,
                            (
                                "Scale AVG: "
                                f"{scale['average']:.2f} "
                                "px/mm"
                            ),
                            (700, 110),
                            GREEN,
                        )


                        # ==============================
                        # SCALE CONSISTENCY
                        # ==============================

                        if (
                            check_scale_consistency(
                                scale
                            )
                        ):

                            put(
                                display,
                                "Scale: OK",
                                (20, 320),
                                GREEN,
                            )


                            # ==========================
                            # CREATE CAMERA REFERENCE
                            # ==========================

                            if (
                                camera_reference
                                is None
                            ):

                                camera_reference = (
                                    create_camera_reference(
                                        frame,
                                        result,
                                        perspective,
                                        scale,
                                    )
                                )


                                # ======================
                                # Roll ยังไม่ได้ตั้งค่า
                                # ======================

                                camera_reference[
                                    "camera_roll_deg"
                                ] = 0.0


                                camera_reference[
                                    "roll_source"
                                ] = "not_set"


                                adjust_roll = 0.0


                                tilt_history.clear()


                                scene_roll = None


                                # ======================
                                # เปิด Tilt Adjustment
                                # ======================

                                open_tilt_window()


                                system_state = (
                                    SystemState
                                    .CAMERA_SETUP_COMPLETE
                                )


                                print(
                                    "Camera Reference Created"
                                )


                                print(
                                    camera_reference
                                )


                                print(
                                    "Current State:",
                                    system_state,
                                )


                        # ==============================
                        # Scale ไม่ Consistent
                        # ==============================

                        else:

                            put(
                                display,
                                "Scale: NOT CONSISTENT",
                                (20, 320),
                                RED,
                            )


                        # ==============================
                        # แสดง Warped Card
                        # ==============================

                        cv2.imshow(
                            "PostGuard - Warped Card",
                            perspective[
                                "image"
                            ],
                        )


            # ==============================================
            # DEBUG INFORMATION
            # ==============================================

            put(
                display,
                (
                    "Contours: "
                    f"{debug['contours']}"
                ),
                (20, 405),
                WHITE,
            )


            put(
                display,
                (
                    f"Size: "
                    f"{debug['passed_size']} "

                    f"4-corner: "
                    f"{debug['passed_4_corners']} "

                    f"Angles: "
                    f"{debug['passed_angles']} "

                    f"Fit: "
                    f"{debug['passed_fit']} "

                    f"Inside: "
                    f"{debug['passed_inside']}"
                ),
                (20, 440),
                WHITE,
            )


            cv2.imshow(
                "PostGuard - Edge Debug",
                edges,
            )


        # ==================================================
        # STATE 2
        # CAMERA SETUP COMPLETE
        # ==================================================
        #
        # ใช้ปรับ Camera Roll
        # ==================================================

        elif (
            system_state
            == SystemState.CAMERA_SETUP_COMPLETE
        ):

            # ==============================================
            # ปิด Debug Window จาก State ก่อนหน้า
            # ==============================================

            if not debug_windows_closed:

                for name in (
                    "PostGuard - Edge Debug",
                    "PostGuard - Warped Card",
                ):

                    try:

                        cv2.destroyWindow(
                            name
                        )

                    except cv2.error:

                        pass


                debug_windows_closed = True


            # ==============================================
            # อ่านตำแหน่ง Slider
            # ==============================================

            slider = cv2.getTrackbarPos(
                "Tilt",
                TILT_WINDOW,
            )


            # ==============================================
            # แปลง Slider → Degree
            # ==============================================

            adjust_roll = (
                SLIDER_CENTER
                - slider
            ) * 0.5


            # ==============================================
            # ตรวจ Scene Tilt
            # ==============================================

            measured = estimate_scene_tilt(
                frame
            )


            if measured is not None:

                tilt_history.append(
                    measured
                )


            # ==============================================
            # Median หลาย Frame
            #
            # ต้องมีอย่างน้อย 5 ค่า
            # ==============================================

            scene_roll = (

                float(
                    np.median(
                        tilt_history
                    )
                )

                if len(
                    tilt_history
                ) >= 5

                else None

            )


            # ==============================================
            # หมุนภาพตาม Slider
            # ==============================================

            display = level_frame(
                frame,
                adjust_roll,
            )


            # ==============================================
            # วาด Grid ช่วยดูแนวระดับ
            # ==============================================

            draw_level_grid(
                display
            )


            put(
                display,
                (
                    "Tilt correction: "
                    f"{adjust_roll:+.1f} deg"
                ),
                (20, 40),
                WHITE,
            )


            # ==============================================
            # ถ้าหา Scene Line ไม่ได้
            # ==============================================

            if scene_roll is None:

                put(
                    display,
                    (
                        "Remaining: ? "
                        "(no clear lines, "
                        "adjust by eye)"
                    ),
                    (20, 75),
                    YELLOW,
                )


            # ==============================================
            # มี Scene Tilt
            # ==============================================

            else:

                remaining = (
                    scene_roll
                    - adjust_roll
                )


                if (
                    abs(
                        remaining
                    )
                    <= 0.5
                ):

                    color = GREEN

                else:

                    color = YELLOW


                put(
                    display,
                    (
                        "Remaining: "
                        f"{remaining:+.1f} "
                        "deg (aim for 0)"
                    ),
                    (20, 75),
                    color,
                )


            put(
                display,
                (
                    "+ = drag slider LEFT, "
                    "- = drag RIGHT"
                ),
                (20, 110),
                WHITE,
            )


            put(
                display,
                (
                    "SPACE = auto set   "
                    "ENTER = confirm   "
                    "BACKSPACE = redo"
                ),
                (20, 145),
                WHITE,
            )


        # ==================================================
        # STATE 3
        # PERSONAL BASELINE
        # ==================================================

        elif (
            system_state
            == SystemState.PERSONAL_BASELINE
        ):

            put(
                display,
                "Personal Baseline",
                (20, 40),
                YELLOW,
            )


            put(
                display,
                (
                    "Sit upright and "
                    "look forward"
                ),
                (20, 75),
                WHITE,
            )


            # ==============================================
            # MEDIAPIPE POSE DETECTION
            # ==============================================

            pose_landmarks = (
                pose_detector.detect(
                    frame
                )
            )


            # ==============================================
            # ไม่พบ Pose
            # ==============================================

            if (
                pose_landmarks
                is None
            ):

                put(
                    display,
                    "Pose: NOT FOUND",
                    (20, 110),
                    RED,
                )


            # ==============================================
            # พบ Pose
            # ==============================================

            else:

                put(
                    display,
                    "Pose: OK",
                    (20, 110),
                    GREEN,
                )


                # Debug
                print(
                    pose_landmarks
                )


        # ==================================================
        # DISPLAY
        # ==========================================================

        cv2.imshow(
            window,
            display,
        )


        key = (
            cv2.waitKey(1)
            & 0xFF
        )


        # ==================================================
        # QUIT
        #
        # Q / q / ESC
        # ==========================================================

        if key in (
            ord("q"),
            ord("Q"),
            27,
        ):

            break


        # ==================================================
        # KEY CONTROL
        # เฉพาะ CAMERA_SETUP_COMPLETE
        # ==========================================================

        if (
            system_state
            == SystemState.CAMERA_SETUP_COMPLETE
        ):

            # ==============================================
            # SPACE
            #
            # Auto Set จาก Scene Roll
            # ==============================================

            if (
                key == 32

                and

                scene_roll
                is not None
            ):

                pos = int(
                    round(
                        SLIDER_CENTER
                        - 2
                        * scene_roll
                    )
                )


                pos = max(
                    0,
                    min(
                        SLIDER_MAX,
                        pos,
                    ),
                )


                cv2.setTrackbarPos(
                    "Tilt",
                    TILT_WINDOW,
                    pos,
                )


            # ==============================================
            # ENTER
            #
            # Confirm Camera Roll
            # ==============================================

            elif key == 13:

                camera_reference[
                    "camera_roll_deg"
                ] = adjust_roll


                camera_reference[
                    "roll_source"
                ] = "user_adjusted"


                close_tilt_window()


                system_state = (
                    SystemState
                    .PERSONAL_BASELINE
                )


                print(
                    "Camera roll saved:",
                    adjust_roll,
                )


                print(
                    "Current State:",
                    system_state,
                )


            # ==============================================
            # BACKSPACE / R
            #
            # Reset Setup
            # ==============================================

            elif key in (
                8,
                ord("r"),
                ord("R"),
            ):

                camera_reference = None


                stable_count = 0


                close_tilt_window()


                system_state = (
                    SystemState
                    .CAMERA_SETUP
                )


                print(
                    "Current State:",
                    system_state,
                )


    # ======================================================
    # CLEANUP
    # ======================================================

    pose_detector.close()

    cap.release()

    cv2.destroyAllWindows()


# ==========================================================
# RUN
# ==========================================================

if __name__ == "__main__":

    main()