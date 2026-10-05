from collections import deque

import cv2
import numpy as np

from system_state import SystemState

from camera_setup.guide import get_guide_bounds, draw_guide
from camera_setup.card_detection import detect_rectangle
from camera_setup.card_validation import check_position, check_size
from camera_setup.card_perspective import warp_card, calculate_pixel_scale
from camera_setup.camera_reference import (
    check_scale_consistency,
    create_camera_reference
)
from camera_setup.camera_alignment import check_alignment
from camera_setup.camera_roll import (
    level_frame,
    draw_level_grid,
    estimate_scene_tilt
)

STABLE_FRAMES = 15   # ต้องผ่านต่อเนื่องกี่ frame ถึงนับว่านิ่ง

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
BLUE = (255, 150, 0)

TILT_WINDOW = "Tilt Adjust"
SLIDER_CENTER = 60    # ตำแหน่ง slider = ไม่แก้ (0 องศา)
SLIDER_MAX = 120      # slider 0..120 = +30..-30 องศา (ขั้นละ 0.5)


def put(img, text, pos, color):
    """แสดงข้อความบน Frame"""
    cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def nothing(_):
    pass


def open_tilt_window():
    """เปิดหน้าต่าง slider สำหรับปรับกล้องเอียง"""
    cv2.namedWindow(TILT_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(TILT_WINDOW, 520, 80)
    cv2.createTrackbar("Tilt", TILT_WINDOW, SLIDER_CENTER, SLIDER_MAX, nothing)


def close_tilt_window():
    try:
        cv2.destroyWindow(TILT_WINDOW)
    except cv2.error:
        pass


def main():

    # =========================
    # เปิดกล้อง
    # =========================
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Can't open camera")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    window = "PostGuard - Camera Setup"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    # =========================
    # ตัวแปรของระบบ
    # =========================
    stable_count = 0
    camera_reference = None
    system_state = SystemState.CAMERA_SETUP
    debug_windows_closed = False

    adjust_roll = 0.0                  # ค่าแก้กล้องเอียงที่ผู้ใช้ปรับเอง (องศา)
    tilt_history = deque(maxlen=15)    # เก็บค่าเอียงของเส้นในห้องหลาย frame
    scene_roll = None                  # ค่ากลางที่วัดได้จากห้อง (None = วัดไม่ได้)

    # =========================
    # Main Loop
    # =========================
    while True:

        ret, frame = cap.read()

        if not ret:
            print("Error: Can't read frame")
            break

        # Mirror Webcam
        frame = cv2.flip(frame, 1)

        # หลัง Setup เสร็จ: หมุนภาพแก้กล้องเอียงก่อนใช้งานต่อ
        if (camera_reference is not None
                and system_state == SystemState.PERSONAL_BASELINE):
            frame = level_frame(frame, camera_reference["camera_roll_deg"])

        display = frame.copy()

        # ==========================================================
        # STATE 1 : CAMERA SETUP
        # ==========================================================
        if system_state == SystemState.CAMERA_SETUP:

            debug_windows_closed = False

            bounds = get_guide_bounds(frame)
            result, edges, debug = detect_rectangle(frame, bounds)
            draw_guide(display, bounds)

            card_valid = False

            # ---------- ไม่พบสี่เหลี่ยม ----------
            if result is None:

                stable_count = 0
                put(display, "Not found", (20, 40), RED)

            # ---------- พบสี่เหลี่ยมแต่ไม่ใช่การ์ด ----------
            elif not result["is_card"]:

                stable_count = 0

                cv2.drawContours(display, [result["box"]], -1, BLUE, 3)
                put(display, "Rectangle found (not a card)", (20, 40), BLUE)
                put(display,
                    f"ratio={result['ratio']:.2f} "
                    f"fill={result['fill']:.0%} "
                    f"fit={result['fit']:.0%}",
                    (20, 75), WHITE)

            # ---------- พบการ์ด ----------
            else:

                cv2.drawContours(display, [result["box"]], -1, GREEN, 3)
                put(display, "Reference Card Candidate", (20, 40), GREEN)
                put(display,
                    f"ratio={result['ratio']:.2f} "
                    f"fill={result['fill']:.0%} "
                    f"fit={result['fit']:.0%}",
                    (20, 75), WHITE)

                # ----- Position -----
                position = check_position(result["box"], bounds)

                if position["valid"]:
                    put(display, "Position: OK", (20, 110), GREEN)
                else:
                    put(display, f"Position: {position['direction']}",
                        (20, 110), YELLOW)

                # ----- Size -----
                size = check_size(result["fill"])

                if size["valid"]:
                    put(display, "Card Size: OK", (20, 145), GREEN)
                else:
                    put(display, f"Card Size: {size['direction']}",
                        (20, 145), YELLOW)

                # ----- Alignment -----
                # max_roll=45: ไม่ปฏิเสธการ์ดที่เอียง ตรวจเฉพาะ Perspective
                alignment = check_alignment(result["box"], bounds, max_roll=45.0)

                put(display, f"Card tilt: {alignment['roll_error']:.2f} deg",
                    (20, 215), WHITE)
                put(display,
                    f"H-Perspective: {alignment['horizontal_perspective']:.1%}",
                    (20, 250), WHITE)
                put(display,
                    f"V-Perspective: {alignment['vertical_perspective']:.1%}",
                    (20, 285), WHITE)

                # ----- Stability -----
                if (position["valid"]
                        and size["valid"]
                        and alignment["valid"]):
                    stable_count += 1
                else:
                    stable_count = 0

                stable_count = min(stable_count, STABLE_FRAMES)

                if stable_count >= STABLE_FRAMES:
                    card_valid = True

                if not card_valid:

                    put(display, f"Stability: {stable_count}/{STABLE_FRAMES}",
                        (20, 320), YELLOW)

                # ----- Card Valid -----
                else:

                    put(display, "Reference Card Valid", (20, 180), GREEN)

                    perspective = warp_card(frame, result["box"])

                    if perspective is not None:

                        # ----- Pixel Scale -----
                        scale = calculate_pixel_scale(
                            perspective["width_px"],
                            perspective["height_px"]
                        )

                        put(display, f"Scale X: {scale['x']:.2f} px/mm",
                            (700, 40), GREEN)
                        put(display, f"Scale Y: {scale['y']:.2f} px/mm",
                            (700, 75), GREEN)
                        put(display, f"Scale AVG: {scale['average']:.2f} px/mm",
                            (700, 110), GREEN)

                        # ----- Scale Consistency -----
                        if check_scale_consistency(scale):

                            put(display, "Scale: OK", (20, 320), GREEN)

                            # ----- สร้าง Camera Reference (ครั้งเดียว) -----
                            if camera_reference is None:

                                camera_reference = create_camera_reference(
                                    frame,
                                    result,
                                    perspective,
                                    scale
                                )

                                # ยังไม่รู้ค่ากล้องเอียง ให้ผู้ใช้ปรับในหน้าถัดไป
                                camera_reference["camera_roll_deg"] = 0.0
                                camera_reference["roll_source"] = "not_set"
                                adjust_roll = 0.0
                                tilt_history.clear()
                                scene_roll = None

                                open_tilt_window()
                                system_state = SystemState.CAMERA_SETUP_COMPLETE

                                print("Camera Reference Created")
                                print(camera_reference)
                                print("Current State:", system_state)

                        else:

                            put(display, "Scale: NOT CONSISTENT",
                                (20, 320), RED)

                        cv2.imshow("PostGuard - Warped Card",
                                   perspective["image"])

            # ---------- Debug Information ----------
            put(display, f"Contours: {debug['contours']}", (20, 405), WHITE)

            put(display,
                f"Size: {debug['passed_size']} "
                f"4-corner: {debug['passed_4_corners']} "
                f"Angles: {debug['passed_angles']} "
                f"Fit: {debug['passed_fit']} "
                f"Inside: {debug['passed_inside']}",
                (20, 440), WHITE)

            cv2.imshow("PostGuard - Edge Debug", edges)

        # ==========================================================
        # STATE 2 : CAMERA SETUP COMPLETE
        # ผู้ใช้ลาก slider ปรับกล้องเอียง โดยดูตัวเลข Remaining + เส้นตาราง
        # ==========================================================
        elif system_state == SystemState.CAMERA_SETUP_COMPLETE:

            if not debug_windows_closed:

                for name in ("PostGuard - Edge Debug",
                             "PostGuard - Warped Card"):
                    try:
                        cv2.destroyWindow(name)
                    except cv2.error:
                        pass

                debug_windows_closed = True

            # อ่านค่า slider: ขวา = หมุนภาพตามเข็ม, ซ้าย = ทวนเข็ม
            slider = cv2.getTrackbarPos("Tilt", TILT_WINDOW)
            adjust_roll = (SLIDER_CENTER - slider) * 0.5

            # วัดความเอียงของเส้นในห้อง (จากภาพดิบ ไม่ขึ้นกับ slider)
            measured = estimate_scene_tilt(frame)
            if measured is not None:
                tilt_history.append(measured)

            scene_roll = (float(np.median(tilt_history))
                          if len(tilt_history) >= 5 else None)

            # แสดงภาพที่หมุนแก้แล้ว พร้อมเส้นตาราง
            display = level_frame(frame, adjust_roll)
            draw_level_grid(display)

            put(display, f"Tilt correction: {adjust_roll:+.1f} deg",
                (20, 40), WHITE)

            if scene_roll is None:
                put(display, "Remaining: ? (no clear lines, adjust by eye)",
                    (20, 75), YELLOW)
            else:
                remaining = scene_roll - adjust_roll
                color = GREEN if abs(remaining) <= 0.5 else YELLOW
                put(display, f"Remaining: {remaining:+.1f} deg (aim for 0)",
                    (20, 75), color)

            put(display, "+ = drag slider LEFT,  - = drag RIGHT",
                (20, 110), WHITE)
            put(display, "SPACE = auto set   ENTER = confirm   BACKSPACE = redo",
                (20, 145), WHITE)

        # ==========================================================
        # STATE 3 : PERSONAL BASELINE
        # ==========================================================
        elif system_state == SystemState.PERSONAL_BASELINE:

            put(display, "Personal Baseline", (20, 40), YELLOW)
            put(display, "Sit upright and look forward", (20, 75), WHITE)

        # ==========================================================
        # แสดงผล + ปุ่มกด
        # ==========================================================
        cv2.imshow(window, display)

        key = cv2.waitKey(1) & 0xFF

        # q / Q / ESC = ออก
        if key in (ord("q"), ord("Q"), 27):
            break

        if system_state == SystemState.CAMERA_SETUP_COMPLETE:

            # SPACE: ให้ระบบตั้ง slider ตามเส้นในห้อง (ผู้ใช้ยังต้องตรวจและยืนยันเอง)
            if key == 32 and scene_roll is not None:
                pos = int(round(SLIDER_CENTER - 2 * scene_roll))
                cv2.setTrackbarPos("Tilt", TILT_WINDOW,
                                   max(0, min(SLIDER_MAX, pos)))

            # ENTER: ผู้ใช้ยืนยัน เก็บค่า แล้วไปต่อ
            elif key == 13:
                camera_reference["camera_roll_deg"] = adjust_roll
                camera_reference["roll_source"] = "user_adjusted"
                close_tilt_window()
                system_state = SystemState.PERSONAL_BASELINE
                print("Camera roll saved:", adjust_roll)
                print("Current State:", system_state)

            # BACKSPACE (หรือ r/R): ตั้งค่าใหม่ทั้งหมด
            elif key in (8, ord("r"), ord("R")):
                camera_reference = None
                stable_count = 0
                close_tilt_window()
                system_state = SystemState.CAMERA_SETUP
                print("Current State:", system_state)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()