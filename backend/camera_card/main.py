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
    create_camera_reference,
)
from camera_setup.camera_alignment import check_alignment
from camera_setup.camera_roll import (
    level_frame,
    draw_level_grid,
    estimate_scene_tilt,
)

from mediapipe_detection.detection_pipeline import DetectionPipeline


# ==========================================================
# CONFIG
# ==========================================================

STABLE_FRAMES = 15

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
BLUE = (255, 150, 0)

TILT_WINDOW = "Tilt Adjust"
SLIDER_CENTER = 60
SLIDER_MAX = 120


# ==========================================================
# UI HELPERS
# ==========================================================

def put(img, text, pos, color):
    cv2.putText(
        img,
        str(text),
        pos,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2,
        cv2.LINE_AA,
    )


def nothing(_):
    pass


def open_tilt_window():
    cv2.namedWindow(TILT_WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(TILT_WINDOW, 520, 80)
    cv2.createTrackbar(
        "Tilt",
        TILT_WINDOW,
        SLIDER_CENTER,
        SLIDER_MAX,
        nothing,
    )


def close_tilt_window():
    try:
        cv2.destroyWindow(TILT_WINDOW)
    except cv2.error:
        pass


# ==========================================================
# DETECTION HELPERS
# ==========================================================

def get_feature_value(result, feature_name):
    if not isinstance(result, dict):
        return None

    features = result.get("features")

    if not isinstance(features, dict):
        return None

    feature = features.get(feature_name)

    if not isinstance(feature, dict):
        return None

    if feature.get("valid") is not True:
        return None

    value = feature.get("value")

    if not isinstance(value, (int, float)):
        return None

    return float(value)


def format_feature(value, unit):
    if value is None:
        return "N/A"

    return f"{value:.2f} {unit}"


def get_context_text(result):
    if not isinstance(result, dict):
        return "UNKNOWN"

    context = result.get("context") or {}

    state = context.get("state")

    if state is None:
        state = context.get("status")

    if state is None:
        return "UNKNOWN"

    if hasattr(state, "value"):
        state = state.value

    return str(state)


def posture_evaluation_allowed(result):
    if not isinstance(result, dict):
        return False

    context = result.get("context") or {}

    return context.get("allow_posture_evaluation") is True


# ==========================================================
# FRAME FLOW
# ==========================================================

def build_detection_frame(raw_frame, mirror_roll_deg):
    """
    DetectionPipeline ต้องรับภาพ UNMIRRORED

    Camera Setup เดิมคำนวณ Camera Roll บนภาพ Mirror
    การ Mirror จะกลับเครื่องหมายของมุม Roll
    ดังนั้น Raw Detection Frame ต้องใช้ -mirror_roll_deg
    """

    return level_frame(
        raw_frame,
        -float(mirror_roll_deg),
    )


def build_display_frame(raw_frame, mirror_roll_deg):
    """ภาพสำหรับผู้ใช้ดู: Mirror แล้วแก้ Roll แบบเดิม"""

    mirrored = cv2.flip(raw_frame, 1)

    return level_frame(
        mirrored,
        float(mirror_roll_deg),
    )


# ==========================================================
# MAIN
# ==========================================================

def main():
    # ------------------------------------------------------
    # Camera
    # ------------------------------------------------------

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Can't open camera")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # ------------------------------------------------------
    # DetectionPipeline
    #
    # Pipeline จัดการ model path เอง
    # ไม่ต้องสร้าง PoseDetector ใน main.py อีก
    # ------------------------------------------------------

    try:
        detection_pipeline = DetectionPipeline()

    except Exception as error:
        cap.release()
        print("Error: Cannot start DetectionPipeline")
        print(error)
        raise

    print("DetectionPipeline ready")

    # ------------------------------------------------------
    # Window
    # ------------------------------------------------------

    window = "PostGuard - Camera Setup"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    # ------------------------------------------------------
    # Runtime State
    # ------------------------------------------------------

    stable_count = 0
    camera_reference = None
    system_state = SystemState.CAMERA_SETUP
    debug_windows_closed = False

    adjust_roll = 0.0
    tilt_history = deque(maxlen=15)
    scene_roll = None

    try:
        while True:
            # ==================================================
            # RAW CAMERA FRAME
            # ==================================================

            ret, raw_frame = cap.read()

            if not ret:
                print("Error: Can't read frame")
                break

            # Camera Setup เดิมทำงานบนภาพ Mirror
            setup_frame = cv2.flip(raw_frame, 1)
            frame = setup_frame
            display = frame.copy()

            # ==================================================
            # STATE 1 : CAMERA SETUP
            # ==================================================

            if system_state == SystemState.CAMERA_SETUP:
                debug_windows_closed = False

                bounds = get_guide_bounds(frame)
                result, edges, debug = detect_rectangle(frame, bounds)
                draw_guide(display, bounds)

                card_valid = False

                # ----------------------------------------------
                # Not found
                # ----------------------------------------------

                if result is None:
                    stable_count = 0
                    put(display, "Not found", (20, 40), RED)

                # ----------------------------------------------
                # Rectangle but not card
                # ----------------------------------------------

                elif not result["is_card"]:
                    stable_count = 0

                    cv2.drawContours(
                        display,
                        [result["box"]],
                        -1,
                        BLUE,
                        3,
                    )

                    put(
                        display,
                        "Rectangle found (not a card)",
                        (20, 40),
                        BLUE,
                    )

                    put(
                        display,
                        (
                            f"ratio={result['ratio']:.2f} "
                            f"fill={result['fill']:.0%} "
                            f"fit={result['fit']:.0%}"
                        ),
                        (20, 75),
                        WHITE,
                    )

                # ----------------------------------------------
                # Card candidate
                # ----------------------------------------------

                else:
                    cv2.drawContours(
                        display,
                        [result["box"]],
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
                            f"ratio={result['ratio']:.2f} "
                            f"fill={result['fill']:.0%} "
                            f"fit={result['fit']:.0%}"
                        ),
                        (20, 75),
                        WHITE,
                    )

                    # Position
                    position = check_position(
                        result["box"],
                        bounds,
                    )

                    if position["valid"]:
                        put(
                            display,
                            "Position: OK",
                            (20, 110),
                            GREEN,
                        )
                    else:
                        put(
                            display,
                            f"Position: {position['direction']}",
                            (20, 110),
                            YELLOW,
                        )

                    # Size
                    size = check_size(result["fill"])

                    if size["valid"]:
                        put(
                            display,
                            "Card Size: OK",
                            (20, 145),
                            GREEN,
                        )
                    else:
                        put(
                            display,
                            f"Card Size: {size['direction']}",
                            (20, 145),
                            YELLOW,
                        )

                    # Alignment
                    alignment = check_alignment(
                        result["box"],
                        bounds,
                        max_roll=45.0,
                    )

                    put(
                        display,
                        f"Card tilt: {alignment['roll_error']:.2f} deg",
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

                    # Stability
                    if (
                        position["valid"]
                        and size["valid"]
                        and alignment["valid"]
                    ):
                        stable_count += 1
                    else:
                        stable_count = 0

                    stable_count = min(
                        stable_count,
                        STABLE_FRAMES,
                    )

                    if stable_count >= STABLE_FRAMES:
                        card_valid = True

                    if not card_valid:
                        put(
                            display,
                            (
                                "Stability: "
                                f"{stable_count}/{STABLE_FRAMES}"
                            ),
                            (20, 320),
                            YELLOW,
                        )

                    # ------------------------------------------
                    # Card valid
                    # ------------------------------------------

                    else:
                        put(
                            display,
                            "Reference Card Valid",
                            (20, 180),
                            GREEN,
                        )

                        perspective = warp_card(
                            frame,
                            result["box"],
                        )

                        if perspective is not None:
                            scale = calculate_pixel_scale(
                                perspective["width_px"],
                                perspective["height_px"],
                            )

                            put(
                                display,
                                f"Scale X: {scale['x']:.2f} px/mm",
                                (700, 40),
                                GREEN,
                            )

                            put(
                                display,
                                f"Scale Y: {scale['y']:.2f} px/mm",
                                (700, 75),
                                GREEN,
                            )

                            put(
                                display,
                                (
                                    "Scale AVG: "
                                    f"{scale['average']:.2f} px/mm"
                                ),
                                (700, 110),
                                GREEN,
                            )

                            if check_scale_consistency(scale):
                                put(
                                    display,
                                    "Scale: OK",
                                    (20, 320),
                                    GREEN,
                                )

                                if camera_reference is None:
                                    camera_reference = (
                                        create_camera_reference(
                                            frame,
                                            result,
                                            perspective,
                                            scale,
                                        )
                                    )

                                    camera_reference[
                                        "camera_roll_deg"
                                    ] = 0.0

                                    camera_reference[
                                        "roll_source"
                                    ] = "not_set"

                                    adjust_roll = 0.0
                                    tilt_history.clear()
                                    scene_roll = None

                                    open_tilt_window()

                                    system_state = (
                                        SystemState.CAMERA_SETUP_COMPLETE
                                    )

                                    print("Camera Reference Created")
                                    print(camera_reference)
                                    print("Current State:", system_state)

                            else:
                                put(
                                    display,
                                    "Scale: NOT CONSISTENT",
                                    (20, 320),
                                    RED,
                                )

                            cv2.imshow(
                                "PostGuard - Warped Card",
                                perspective["image"],
                            )

                # Debug
                put(
                    display,
                    f"Contours: {debug['contours']}",
                    (20, 405),
                    WHITE,
                )

                put(
                    display,
                    (
                        f"Size: {debug['passed_size']} "
                        f"4-corner: {debug['passed_4_corners']} "
                        f"Angles: {debug['passed_angles']} "
                        f"Fit: {debug['passed_fit']} "
                        f"Inside: {debug['passed_inside']}"
                    ),
                    (20, 440),
                    WHITE,
                )

                cv2.imshow(
                    "PostGuard - Edge Debug",
                    edges,
                )

            # ==================================================
            # STATE 2 : CAMERA SETUP COMPLETE
            # ==================================================

            elif system_state == SystemState.CAMERA_SETUP_COMPLETE:
                if not debug_windows_closed:
                    for name in (
                        "PostGuard - Edge Debug",
                        "PostGuard - Warped Card",
                    ):
                        try:
                            cv2.destroyWindow(name)
                        except cv2.error:
                            pass

                    debug_windows_closed = True

                slider = cv2.getTrackbarPos(
                    "Tilt",
                    TILT_WINDOW,
                )

                adjust_roll = (
                    SLIDER_CENTER - slider
                ) * 0.5

                measured = estimate_scene_tilt(frame)

                if measured is not None:
                    tilt_history.append(measured)

                scene_roll = (
                    float(np.median(tilt_history))
                    if len(tilt_history) >= 5
                    else None
                )

                display = level_frame(
                    frame,
                    adjust_roll,
                )

                draw_level_grid(display)

                put(
                    display,
                    f"Tilt correction: {adjust_roll:+.1f} deg",
                    (20, 40),
                    WHITE,
                )

                if scene_roll is None:
                    put(
                        display,
                        (
                            "Remaining: ? "
                            "(no clear lines, adjust by eye)"
                        ),
                        (20, 75),
                        YELLOW,
                    )
                else:
                    remaining = scene_roll - adjust_roll

                    color = (
                        GREEN
                        if abs(remaining) <= 0.5
                        else YELLOW
                    )

                    put(
                        display,
                        (
                            f"Remaining: {remaining:+.1f} "
                            "deg (aim for 0)"
                        ),
                        (20, 75),
                        color,
                    )

                put(
                    display,
                    "+ = drag slider LEFT, - = drag RIGHT",
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
            # STATE 3 : PERSONAL BASELINE
            #
            # รอบนี้ยังไม่เก็บ baseline จริง
            # ใช้ตรวจ integration ของ DetectionPipeline ก่อน
            # ==================================================

            elif system_state == SystemState.PERSONAL_BASELINE:
                if camera_reference is None:
                    print("Error: camera_reference is missing")
                    system_state = SystemState.CAMERA_SETUP
                    continue

                camera_roll_deg = camera_reference[
                    "camera_roll_deg"
                ]

                # ------------------------------------------
                # Detection Frame
                # UNMIRRORED + Roll Corrected
                # ------------------------------------------

                detection_frame = build_detection_frame(
                    raw_frame,
                    camera_roll_deg,
                )

                # ------------------------------------------
                # Display Frame
                # MIRRORED + Roll Corrected
                # ------------------------------------------

                display = build_display_frame(
                    raw_frame,
                    camera_roll_deg,
                )

                detection_result = (
                    detection_pipeline.process_frame(
                        detection_frame
                    )
                )

                shoulder_tilt = get_feature_value(
                    detection_result,
                    "shoulder_tilt",
                )

                neck_lateral_tilt = get_feature_value(
                    detection_result,
                    "neck_lateral_tilt",
                )

                neck_flexion = get_feature_value(
                    detection_result,
                    "neck_flexion",
                )

                eye_distance = get_feature_value(
                    detection_result,
                    "eye_distance",
                )

                context_text = get_context_text(
                    detection_result
                )

                allow_posture = posture_evaluation_allowed(
                    detection_result
                )

                put(
                    display,
                    "Personal Baseline",
                    (20, 40),
                    YELLOW,
                )

                put(
                    display,
                    "Sit upright and look forward",
                    (20, 75),
                    WHITE,
                )

                put(
                    display,
                    f"Context: {context_text}",
                    (20, 115),
                    GREEN if allow_posture else YELLOW,
                )

                put(
                    display,
                    (
                        "Evaluation: "
                        f"{'ALLOW' if allow_posture else 'WAIT'}"
                    ),
                    (20, 150),
                    GREEN if allow_posture else YELLOW,
                )

                put(
                    display,
                    (
                        "Shoulder Tilt: "
                        f"{format_feature(shoulder_tilt, 'deg')}"
                    ),
                    (20, 200),
                    WHITE,
                )

                put(
                    display,
                    (
                        "Neck Lateral: "
                        f"{format_feature(neck_lateral_tilt, 'deg')}"
                    ),
                    (20, 235),
                    WHITE,
                )

                put(
                    display,
                    (
                        "Neck Flexion: "
                        f"{format_feature(neck_flexion, 'deg')}"
                    ),
                    (20, 270),
                    WHITE,
                )

                put(
                    display,
                    (
                        "Eye Distance: "
                        f"{format_feature(eye_distance, 'px')}"
                    ),
                    (20, 305),
                    WHITE,
                )

                put(
                    display,
                    "Baseline collection will be added next.",
                    (20, 355),
                    YELLOW,
                )

            # ==================================================
            # DISPLAY + KEYBOARD
            # ==================================================

            cv2.imshow(
                window,
                display,
            )

            key = cv2.waitKey(1) & 0xFF

            if key in (
                ord("q"),
                ord("Q"),
                27,
            ):
                break

            # --------------------------------------------------
            # Key control in Camera Setup Complete
            # --------------------------------------------------

            if system_state == SystemState.CAMERA_SETUP_COMPLETE:
                # SPACE = Auto Set
                if key == 32 and scene_roll is not None:
                    pos = int(
                        round(
                            SLIDER_CENTER
                            - 2 * scene_roll
                        )
                    )

                    cv2.setTrackbarPos(
                        "Tilt",
                        TILT_WINDOW,
                        max(
                            0,
                            min(
                                SLIDER_MAX,
                                pos,
                            ),
                        ),
                    )

                # ENTER = Confirm Roll
                elif key == 13:
                    camera_reference[
                        "camera_roll_deg"
                    ] = adjust_roll

                    camera_reference[
                        "roll_source"
                    ] = "user_adjusted"

                    close_tilt_window()

                    detection_pipeline.reset_runtime()

                    system_state = SystemState.PERSONAL_BASELINE

                    print(
                        "Camera roll saved:",
                        adjust_roll,
                    )

                    print(
                        "Current State:",
                        system_state,
                    )

                # BACKSPACE / R = Reset
                elif key in (
                    8,
                    ord("r"),
                    ord("R"),
                ):
                    camera_reference = None
                    stable_count = 0

                    close_tilt_window()
                    detection_pipeline.reset_runtime()

                    system_state = SystemState.CAMERA_SETUP

                    print(
                        "Current State:",
                        system_state,
                    )

    finally:
        close_tilt_window()
        detection_pipeline.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
