import sys
import time
from pathlib import Path

import cv2


# ==========================================================
# Project Path
# ==========================================================

CAMERA_CARD_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

if str(CAMERA_CARD_DIR) not in sys.path:

    sys.path.insert(
        0,
        str(CAMERA_CARD_DIR)
    )


from mediapipe_detection.detection_pipeline import (
    DetectionPipeline
)


# ==========================================================
# Configuration
# ==========================================================

CAMERA_INDEX = 0

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard Detection Pipeline"
)


# ==========================================================
# Colors (BGR)
# ==========================================================

WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)
CYAN = (255, 255, 0)


# ==========================================================
# Draw Text
# ==========================================================

def put(
    frame,
    text,
    y,
    color=WHITE,
    x=20,
    scale=0.55,
):
    """
    วาดข้อความบน Frame
    """

    cv2.putText(
        frame,
        str(text),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        1,
        cv2.LINE_AA,
    )


# ==========================================================
# Feature Formatting
# ==========================================================

def format_feature(
    name,
    feature,
):
    """
    แปลง Feature Result เป็นข้อความ
    """

    if not feature.get(
        "valid",
        False,
    ):

        return (
            f"{name}: INVALID "
            f"({feature.get('reason')})"
        )

    value = feature.get(
        "value"
    )

    unit = feature.get(
        "unit"
    )

    status = feature.get(
        "status"
    )

    if value is None:

        return (
            f"{name}: INVALID VALUE"
        )

    return (
        f"{name}: "
        f"{value:+.3f} "
        f"{unit or ''} "
        f"[{status}]"
    )


# ==========================================================
# Shoulder Elevation Formatting
# ==========================================================

def format_shoulder_elevation(
    feature
):
    """
    Shoulder Elevation มีค่าซ้ายและขวา
    """

    if not feature.get(
        "valid",
        False,
    ):

        return (
            "shoulder_elevation: "
            f"INVALID "
            f"({feature.get('reason')})"
        )

    left_value = (
        feature.get(
            "left"
        )
    )

    right_value = (
        feature.get(
            "right"
        )
    )

    return (
        "shoulder_elevation: "
        f"L={left_value:+.3f} "
        f"R={right_value:+.3f} "
        "[validated]"
    )


# ==========================================================
# Start Eye Calibration
# ==========================================================

def start_eye_calibration(
    pipeline
):
    """
    เริ่ม Open-eye Calibration ใหม่

    แยกเป็น function เพื่อให้เรียกได้ทั้ง:
    - ตอนเปิดโปรแกรม
    - SPACE
    - E
    """

    timestamp = (
        time.perf_counter()
    )

    pipeline.start_eye_calibration(
        timestamp=timestamp
    )

    print()
    print(
        "========================================"
    )
    print(
        "EYE CALIBRATION STARTED"
    )
    print(
        "Look straight at the camera."
    )
    print(
        "Keep both eyes naturally open."
    )
    print(
        "Calibration takes about 3 seconds."
    )
    print(
        "========================================"
    )
    print()


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # 1. Open Webcam
    # ======================================================

    capture = cv2.VideoCapture(
        CAMERA_INDEX
    )

    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open webcam"
        )


    # ======================================================
    # 2. Request Resolution
    # ======================================================

    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH,
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT,
    )


    # ======================================================
    # 3. Check Actual Resolution
    # ======================================================

    actual_width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    actual_height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )


    print()
    print(
        "========================================"
    )
    print(
        "POSTGUARD DETECTION PIPELINE TEST"
    )
    print(
        "========================================"
    )

    print(
        "Requested Resolution:",
        f"{CAMERA_WIDTH}x{CAMERA_HEIGHT}",
    )

    print(
        "Actual Resolution:",
        f"{actual_width}x{actual_height}",
    )

    print()

    print(
        "Controls:"
    )

    print(
        "SPACE / E = Start Eye Calibration"
    )

    print(
        "R = Reset Eye Calibration"
    )

    print(
        "Q / ESC = Quit"
    )

    print()


    # ======================================================
    # 4. OpenCV Window
    # ======================================================

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL,
    )

    cv2.resizeWindow(
        WINDOW_NAME,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
    )


    # ======================================================
    # 5. Detection Pipeline
    # ======================================================

    pipeline = (
        DetectionPipeline()
    )


    # ======================================================
    # 6. AUTO START EYE CALIBRATION
    #
    # สำคัญ:
    #
    # รอบก่อน Eye Calibration ไม่เคยเริ่ม
    # เพราะ key E ไม่ถูกส่งเข้า OpenCV
    #
    # รอบนี้เริ่มอัตโนมัติ
    # ======================================================

    start_eye_calibration(
        pipeline
    )


    # ======================================================
    # FPS Tracking
    # ======================================================

    previous_time = (
        time.perf_counter()
    )

    display_fps = 0.0


    try:

        while True:

            # ==================================================
            # Read Frame
            # ==================================================

            success, frame = (
                capture.read()
            )

            if (
                not success
                or frame is None
            ):

                print(
                    "ERROR: Cannot read frame"
                )

                break


            # ==================================================
            # Timestamp
            # ==================================================

            timestamp = (
                time.perf_counter()
            )


            # ==================================================
            # Detection
            #
            # IMPORTANT:
            # ใช้ UNMIRRORED FRAME
            # ==================================================

            result = (
                pipeline.process_frame(
                    frame,
                    timestamp=timestamp,
                )
            )


            # ==================================================
            # FPS
            # ==================================================

            current_time = (
                time.perf_counter()
            )

            delta_time = (
                current_time
                -
                previous_time
            )

            previous_time = (
                current_time
            )

            if delta_time > 0:

                current_fps = (
                    1.0
                    /
                    delta_time
                )

                if display_fps == 0:

                    display_fps = (
                        current_fps
                    )

                else:

                    display_fps = (
                        0.9
                        *
                        display_fps
                        +
                        0.1
                        *
                        current_fps
                    )


            # ==================================================
            # Display
            #
            # Mirror เฉพาะตอนแสดงผล
            # ==================================================

            display = cv2.flip(
                frame.copy(),
                1,
            )


            # ==================================================
            # Basic Status
            # ==================================================

            pose_detected = (
                result[
                    "pose_detected"
                ]
            )

            face_detected = (
                result[
                    "face_detected"
                ]
            )

            header_color = (
                GREEN
                if (
                    pose_detected
                    and
                    face_detected
                )
                else
                YELLOW
            )

            put(
                display,
                (
                    f"Pose: {pose_detected} | "
                    f"Face: {face_detected} | "
                    f"FPS: {display_fps:.1f}"
                ),
                30,
                header_color,
            )


            # ==================================================
            # Features
            # ==================================================

            features = (
                result[
                    "features"
                ]
            )

            y = 60


            # --------------------------------------------------
            # Shoulder Tilt
            # --------------------------------------------------

            feature = (
                features[
                    "shoulder_tilt"
                ]
            )

            put(
                display,
                format_feature(
                    "shoulder_tilt",
                    feature,
                ),
                y,
                GREEN
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Neck Lateral Tilt
            # --------------------------------------------------

            feature = (
                features[
                    "neck_lateral_tilt"
                ]
            )

            put(
                display,
                format_feature(
                    "neck_lateral_tilt",
                    feature,
                ),
                y,
                GREEN
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Neck Flexion
            # --------------------------------------------------

            feature = (
                features[
                    "neck_flexion"
                ]
            )

            put(
                display,
                format_feature(
                    "neck_flexion",
                    feature,
                ),
                y,
                YELLOW
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Head Yaw
            # --------------------------------------------------

            feature = (
                features[
                    "head_yaw"
                ]
            )

            put(
                display,
                format_feature(
                    "head_yaw",
                    feature,
                ),
                y,
                YELLOW
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Forward Head
            # --------------------------------------------------

            feature = (
                features[
                    "forward_head"
                ]
            )

            put(
                display,
                format_feature(
                    "forward_head",
                    feature,
                ),
                y,
                YELLOW
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Torso Orientation
            # --------------------------------------------------

            feature = (
                features[
                    "torso_orientation"
                ]
            )

            put(
                display,
                format_feature(
                    "torso_orientation",
                    feature,
                ),
                y,
                YELLOW
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Eye Distance
            # --------------------------------------------------

            feature = (
                features[
                    "eye_distance"
                ]
            )

            put(
                display,
                format_feature(
                    "eye_distance",
                    feature,
                ),
                y,
                GREEN
                if feature["valid"]
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Shoulder Elevation
            # --------------------------------------------------

            shoulder_elevation = (
                features[
                    "shoulder_elevation"
                ]
            )

            put(
                display,
                format_shoulder_elevation(
                    shoulder_elevation
                ),
                y,
                GREEN
                if shoulder_elevation[
                    "valid"
                ]
                else RED,
            )

            y += 30


            # ==================================================
            # Eye Information
            # ==================================================

            eye = (
                result[
                    "eye"
                ]
            )

            eye_measurement_valid = (
                eye[
                    "measurement_valid"
                ]
            )

            eye_state = (
                eye[
                    "state"
                ]
            )

            calibrated = (
                eye_state[
                    "calibrated"
                ]
            )

            current_eye_state = (
                eye_state[
                    "eye_state"
                ]
            )

            calibration_progress = (
                eye_state[
                    "calibration_progress"
                ]
            )

            calibration_samples = (
                eye_state[
                    "calibration_samples"
                ]
            )


            # --------------------------------------------------
            # Eye Status Color
            # --------------------------------------------------

            if calibrated:

                if (
                    current_eye_state
                    ==
                    "OPEN"
                ):

                    eye_color = GREEN

                elif (
                    current_eye_state
                    ==
                    "CLOSED"
                ):

                    eye_color = RED

                else:

                    eye_color = YELLOW

            else:

                eye_color = YELLOW


            # --------------------------------------------------
            # Eye State
            # --------------------------------------------------

            put(
                display,
                (
                    "Eye: "
                    f"{current_eye_state} | "
                    f"Calibrated: {calibrated}"
                ),
                y,
                eye_color,
            )

            y += 25


            # --------------------------------------------------
            # Calibration Progress
            # --------------------------------------------------

            put(
                display,
                (
                    "Eye calibration: "
                    f"{calibration_progress * 100:.0f}% | "
                    f"samples={calibration_samples}"
                ),
                y,
                eye_color,
            )

            y += 25


            # --------------------------------------------------
            # Measurement Validity
            # --------------------------------------------------

            put(
                display,
                (
                    "Eye measurement valid: "
                    f"{eye_measurement_valid}"
                ),
                y,
                GREEN
                if eye_measurement_valid
                else RED,
            )

            y += 25


            # --------------------------------------------------
            # Raw Eye Openness
            #
            # มีประโยชน์มากตอน debug
            # --------------------------------------------------

            measurement = (
                eye.get(
                    "measurement"
                )
            )

            if measurement is not None:

                right_openness = (
                    measurement.get(
                        "right_eye_openness"
                    )
                )

                left_openness = (
                    measurement.get(
                        "left_eye_openness"
                    )
                )

                put(
                    display,
                    (
                        "Eye openness: "
                        f"R={right_openness:.3f} "
                        f"L={left_openness:.3f}"
                    ),
                    y,
                    CYAN,
                )

                y += 25


            # ==================================================
            # Resolution
            # ==================================================

            h, w = (
                frame.shape[:2]
            )

            put(
                display,
                (
                    f"Frame: {w}x{h}"
                ),
                30,
                CYAN,
                x=950,
            )


            # ==================================================
            # Help
            # ==================================================

            help_y = (
                display.shape[0]
                -
                45
            )

            put(
                display,
                (
                    "SPACE/E: Eye calibration | "
                    "R: Reset | "
                    "Q/ESC: Quit"
                ),
                help_y,
                WHITE,
            )


            # ==================================================
            # Show
            # ==================================================

            cv2.imshow(
                WINDOW_NAME,
                display,
            )


            # ==================================================
            # Keyboard
            # ==================================================

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )


            # --------------------------------------------------
            # Debug Key
            #
            # ถ้ามีปุ่มถูกกด จะแสดง code ใน Terminal
            # --------------------------------------------------

            if key != 255:

                print(
                    "Key code:",
                    key
                )


            # --------------------------------------------------
            # SPACE / E
            # Start Calibration
            # --------------------------------------------------

            if key in (
                32,
                ord("e"),
                ord("E"),
            ):

                start_eye_calibration(
                    pipeline
                )


            # --------------------------------------------------
            # Reset
            # --------------------------------------------------

            elif key in (
                ord("r"),
                ord("R"),
            ):

                pipeline.reset_eye_calibration()

                print()
                print(
                    "Eye calibration RESET"
                )
                print()


            # --------------------------------------------------
            # Quit
            # --------------------------------------------------

            elif key in (
                ord("q"),
                ord("Q"),
                27,
            ):

                break


    finally:

        pipeline.close()

        capture.release()

        cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()