from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

import cv2

from app.services.blink_detection_service import (
    BlinkDetectionService,
)
from app.services.detection_service import (
    DetectionService,
)


# ============================================================
# CONFIGURATION
# ============================================================

CAMERA_INDEX = 0

REQUESTED_WIDTH = 1280
REQUESTED_HEIGHT = 720

PROCESS_EVERY_N_FRAMES = 1

TARGET_BLINKS = 10

TEST_ROUNDS = 3

RESULT_DIR = (
    Path(__file__).resolve().parent
    / "results"
)

WINDOW_NAME = (
    "PostGuard Blink Detection Camera Test"
)


# ============================================================
# HELPER
# ============================================================

def safe_float(
    value,
):
    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def format_float(
    value,
    digits=4,
):
    value = safe_float(
        value
    )

    if value is None:
        return "--"

    return f"{value:.{digits}f}"


def draw_text(
    frame,
    text,
    x,
    y,
    *,
    scale=0.65,
    thickness=2,
):
    cv2.putText(
        frame,
        str(text),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def save_screenshot(
    frame,
    path,
):
    cv2.imwrite(
        str(path),
        frame,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp_text = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    csv_path = (
        RESULT_DIR
        /
        (
            "blink_detection_camera_"
            f"{timestamp_text}.csv"
        )
    )

    summary_path = (
        RESULT_DIR
        /
        (
            "blink_detection_summary_"
            f"{timestamp_text}.txt"
        )
    )

    screenshot_dir = (
        RESULT_DIR
        /
        (
            "blink_detection_images_"
            f"{timestamp_text}"
        )
    )

    screenshot_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # CAMERA
    # ========================================================

    capture = cv2.VideoCapture(
        CAMERA_INDEX
    )

    if not capture.isOpened():

        raise RuntimeError(
            "Unable to open camera."
        )

    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        REQUESTED_WIDTH,
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        REQUESTED_HEIGHT,
    )

    driver_width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    driver_height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    driver_fps = (
        capture.get(
            cv2.CAP_PROP_FPS
        )
    )

    # ========================================================
    # POSTGUARD SERVICES
    # ========================================================

    detector = DetectionService()

    blink_detector = (
        BlinkDetectionService()
    )

    blink_detector.reset(
        preserve_count=False,
        now=time.monotonic(),
    )

    # ========================================================
    # CSV
    # ========================================================

    csv_file = open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8",
    )

    fieldnames = [
        "timestamp",
        "elapsed_seconds",
        "frame_number",
        "round",
        "round_target",
        "calibrated",
        "calibration_status",
        "calibration_progress",
        "eye_state",
        "right_eye_state",
        "left_eye_state",
        "eye_pattern",
        "right_eye_openness",
        "left_eye_openness",
        "mean_eye_openness",
        "right_open_reference",
        "left_open_reference",
        "right_close_threshold",
        "left_close_threshold",
        "right_reopen_threshold",
        "left_reopen_threshold",
        "blink_event",
        "blink_duration_seconds",
        "session_blink_count",
        "round_blink_count",
        "face_detected",
    ]

    writer = csv.DictWriter(
        csv_file,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    # ========================================================
    # RUNTIME STATE
    # ========================================================

    started_at = time.monotonic()

    frame_number = 0

    current_round = 1

    round_start_blinks = 0

    round_results = []

    last_result = None

    screenshot_index = 0

    previous_calibrated = False

    print()
    print("=" * 70)
    print(
        "POSTGUARD REAL-CAMERA BLINK DETECTION TEST"
    )
    print("=" * 70)

    print(
        f"Camera device   : {CAMERA_INDEX}"
    )

    print(
        "Requested       : "
        f"{REQUESTED_WIDTH}x"
        f"{REQUESTED_HEIGHT}"
    )

    print(
        "Driver reported : "
        f"{driver_width}x"
        f"{driver_height}"
    )

    print(
        "FPS reported    : "
        f"{driver_fps:.3f}"
    )

    print()
    print(
        "TEST INSTRUCTIONS"
    )

    print(
        "1. Look straight at the camera."
    )

    print(
        "2. Keep eyes naturally OPEN "
        "during calibration."
    )

    print(
        "3. Wait until Calibration = READY."
    )

    print(
        f"4. Blink naturally "
        f"{TARGET_BLINKS} times per round."
    )

    print(
        f"5. Complete {TEST_ROUNDS} rounds."
    )

    print()
    print(
        "KEYS"
    )

    print(
        "N = finish current round"
    )

    print(
        "S = save screenshot"
    )

    print(
        "R = reset calibration/count"
    )

    print(
        "Q = quit test"
    )

    print("=" * 70)
    print()

    # ========================================================
    # CAMERA LOOP
    # ========================================================

    try:

        while True:

            success, frame = (
                capture.read()
            )

            if (
                not success
                or
                frame is None
            ):

                print(
                    "ERROR: Unable to read camera frame."
                )

                break

            frame_number += 1

            display_frame = (
                frame.copy()
            )

            # =================================================
            # DETECTION
            # =================================================

            if (
                frame_number
                %
                PROCESS_EVERY_N_FRAMES
                ==
                0
            ):

                try:

                    detection_result = (
                        detector.process_frame(
                            frame
                        )
                    )

                    last_result = (
                        blink_detector.process_detection(
                            detection_result,
                            now=time.monotonic(),
                        )
                    )

                except Exception as error:

                    print(
                        "DETECTION ERROR:",
                        error,
                    )

                    last_result = None

            # =================================================
            # CURRENT VALUES
            # =================================================

            calibrated = False
            calibration_status = "--"
            calibration_progress = 0.0

            eye_state = "--"
            right_eye_state = "--"
            left_eye_state = "--"
            eye_pattern = "--"

            right_openness = None
            left_openness = None
            mean_openness = None

            blink_event = False
            blink_duration = None

            face_detected = False

            if last_result is not None:

                calibrated = (
                    last_result.get(
                        "calibrated"
                    )
                    is True
                )

                calibration_status = (
                    last_result.get(
                        "calibration_status"
                    )
                    or
                    "--"
                )

                calibration_progress = (
                    last_result.get(
                        "calibration_progress"
                    )
                    or
                    0.0
                )

                eye_state = (
                    last_result.get(
                        "eye_state"
                    )
                    or
                    "--"
                )

                right_eye_state = (
                    last_result.get(
                        "right_eye_state"
                    )
                    or
                    "--"
                )

                left_eye_state = (
                    last_result.get(
                        "left_eye_state"
                    )
                    or
                    "--"
                )

                eye_pattern = (
                    last_result.get(
                        "eye_pattern"
                    )
                    or
                    "--"
                )

                right_openness = (
                    last_result.get(
                        "right_eye_openness"
                    )
                )

                left_openness = (
                    last_result.get(
                        "left_eye_openness"
                    )
                )

                mean_openness = (
                    last_result.get(
                        "mean_eye_openness"
                    )
                )

                blink_event = (
                    last_result.get(
                        "blink_event"
                    )
                    is True
                )

                blink_duration = (
                    last_result.get(
                        "blink_duration_seconds"
                    )
                )

                face_detected = (
                    eye_state
                    !=
                    "UNKNOWN"
                )

            # =================================================
            # CALIBRATION READY SCREENSHOT
            # =================================================

            if (
                calibrated
                and
                not previous_calibrated
            ):

                calibration_image = (
                    screenshot_dir
                    /
                    "calibration_ready.png"
                )

                save_screenshot(
                    display_frame,
                    calibration_image,
                )

                print(
                    "Calibration READY"
                )

                print(
                    "Open reference R/L:",
                    format_float(
                        last_result.get(
                            "right_open_reference"
                        )
                    ),
                    "/",
                    format_float(
                        last_result.get(
                            "left_open_reference"
                        )
                    ),
                )

            previous_calibrated = (
                calibrated
            )

            # =================================================
            # ROUND COUNT
            # =================================================

            round_blink_count = max(
                0,
                blink_detector.total_blinks
                -
                round_start_blinks,
            )

            # =================================================
            # CSV
            # =================================================

            elapsed = (
                time.monotonic()
                -
                started_at
            )

            writer.writerow(
                {
                    "timestamp": (
                        datetime.now().isoformat()
                    ),

                    "elapsed_seconds": (
                        f"{elapsed:.6f}"
                    ),

                    "frame_number": (
                        frame_number
                    ),

                    "round": (
                        current_round
                    ),

                    "round_target": (
                        TARGET_BLINKS
                    ),

                    "calibrated": (
                        calibrated
                    ),

                    "calibration_status": (
                        calibration_status
                    ),

                    "calibration_progress": (
                        calibration_progress
                    ),

                    "eye_state": (
                        eye_state
                    ),

                    "right_eye_state": (
                        right_eye_state
                    ),

                    "left_eye_state": (
                        left_eye_state
                    ),

                    "eye_pattern": (
                        eye_pattern
                    ),

                    "right_eye_openness": (
                        right_openness
                    ),

                    "left_eye_openness": (
                        left_openness
                    ),

                    "mean_eye_openness": (
                        mean_openness
                    ),

                    "right_open_reference": (
                        last_result.get(
                            "right_open_reference"
                        )
                        if last_result
                        else
                        None
                    ),

                    "left_open_reference": (
                        last_result.get(
                            "left_open_reference"
                        )
                        if last_result
                        else
                        None
                    ),

                    "right_close_threshold": (
                        last_result.get(
                            "right_close_threshold"
                        )
                        if last_result
                        else
                        None
                    ),

                    "left_close_threshold": (
                        last_result.get(
                            "left_close_threshold"
                        )
                        if last_result
                        else
                        None
                    ),

                    "right_reopen_threshold": (
                        last_result.get(
                            "right_reopen_threshold"
                        )
                        if last_result
                        else
                        None
                    ),

                    "left_reopen_threshold": (
                        last_result.get(
                            "left_reopen_threshold"
                        )
                        if last_result
                        else
                        None
                    ),

                    "blink_event": (
                        blink_event
                    ),

                    "blink_duration_seconds": (
                        blink_duration
                    ),

                    "session_blink_count": (
                        blink_detector.total_blinks
                    ),

                    "round_blink_count": (
                        round_blink_count
                    ),

                    "face_detected": (
                        face_detected
                    ),
                }
            )

            # =================================================
            # BLINK EVENT SCREENSHOT
            # =================================================

            if blink_event:

                screenshot_index += 1

                blink_image = (
                    screenshot_dir
                    /
                    (
                        "blink_"
                        f"{screenshot_index:03d}.png"
                    )
                )

                save_screenshot(
                    display_frame,
                    blink_image,
                )

            # =================================================
            # OVERLAY
            # =================================================

            y = 30

            draw_text(
                display_frame,
                "PostGuard Blink Detection Test",
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Calibration: "
                    f"{calibration_status} "
                    f"({calibration_progress * 100:.0f}%)"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Eye State: "
                    f"{eye_state}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Right / Left: "
                    f"{right_eye_state} / "
                    f"{left_eye_state}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Pattern: "
                    f"{eye_pattern}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Right Openness: "
                    f"{format_float(right_openness)}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Left Openness: "
                    f"{format_float(left_openness)}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Blink Event: "
                    f"{blink_event}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Session Blink Count: "
                    f"{blink_detector.total_blinks}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    f"Round: {current_round}/"
                    f"{TEST_ROUNDS}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                (
                    "Round Blink Count: "
                    f"{round_blink_count}/"
                    f"{TARGET_BLINKS}"
                ),
                20,
                y,
            )

            y += 35

            draw_text(
                display_frame,
                "N=Next  S=Screenshot  "
                "R=Reset  Q=Quit",
                20,
                y,
                scale=0.55,
            )

            # =================================================
            # DISPLAY
            # =================================================

            cv2.imshow(
                WINDOW_NAME,
                display_frame,
            )

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )

            # =================================================
            # QUIT
            # =================================================

            if key in (
                ord("q"),
                ord("Q"),
            ):

                print(
                    "Test stopped by user."
                )

                break

            # =================================================
            # MANUAL SCREENSHOT
            # =================================================

            if key in (
                ord("s"),
                ord("S"),
            ):

                screenshot_index += 1

                manual_path = (
                    screenshot_dir
                    /
                    (
                        "manual_"
                        f"{screenshot_index:03d}.png"
                    )
                )

                save_screenshot(
                    display_frame,
                    manual_path,
                )

                print(
                    "Screenshot:",
                    manual_path,
                )

            # =================================================
            # RESET
            # =================================================

            if key in (
                ord("r"),
                ord("R"),
            ):

                blink_detector.reset(
                    preserve_count=False,
                    now=time.monotonic(),
                )

                round_start_blinks = 0

                current_round = 1

                round_results.clear()

                previous_calibrated = False

                print(
                    "Blink detector reset."
                )

            # =================================================
            # NEXT ROUND
            # =================================================

            if key in (
                ord("n"),
                ord("N"),
            ):

                detected = (
                    round_blink_count
                )

                difference = (
                    detected
                    -
                    TARGET_BLINKS
                )

                absolute_error = abs(
                    difference
                )

                round_result = {
                    "round": (
                        current_round
                    ),
                    "target": (
                        TARGET_BLINKS
                    ),
                    "detected": (
                        detected
                    ),
                    "difference": (
                        difference
                    ),
                    "absolute_error": (
                        absolute_error
                    ),
                }

                round_results.append(
                    round_result
                )

                print()
                print(
                    f"ROUND {current_round}"
                )

                print(
                    f"Target   : {TARGET_BLINKS}"
                )

                print(
                    f"Detected : {detected}"
                )

                print(
                    f"Error    : {difference:+d}"
                )

                print(
                    f"Abs Error: {absolute_error}"
                )

                # ---------------------------------------------
                # Save round screenshot
                # ---------------------------------------------

                round_image = (
                    screenshot_dir
                    /
                    (
                        "round_"
                        f"{current_round}_result.png"
                    )
                )

                save_screenshot(
                    display_frame,
                    round_image,
                )

                # ---------------------------------------------
                # FINISHED
                # ---------------------------------------------

                if (
                    current_round
                    >=
                    TEST_ROUNDS
                ):

                    break

                # ---------------------------------------------
                # NEXT
                # ---------------------------------------------

                current_round += 1

                round_start_blinks = (
                    blink_detector.total_blinks
                )

                print()
                print(
                    f"Start Round "
                    f"{current_round}"
                )

    finally:

        csv_file.flush()
        csv_file.close()

        capture.release()

        try:
            detector.close()

        except Exception:
            pass

        cv2.destroyAllWindows()

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print(
        "BLINK DETECTION TEST SUMMARY"
    )
    print("=" * 70)

    if not round_results:

        print(
            "No completed test rounds."
        )

        return

    total_target = sum(
        result[
            "target"
        ]
        for result
        in round_results
    )

    total_detected = sum(
        result[
            "detected"
        ]
        for result
        in round_results
    )

    total_absolute_error = sum(
        result[
            "absolute_error"
        ]
        for result
        in round_results
    )

    mean_absolute_error = (
        total_absolute_error
        /
        len(
            round_results
        )
    )

    count_accuracy = (
        max(
            0.0,
            (
                1.0
                -
                (
                    total_absolute_error
                    /
                    total_target
                )
            )
            *
            100.0,
        )
        if total_target > 0
        else 0.0
    )

    summary_lines = []

    for result in round_results:

        line = (
            f"Round {result['round']}: "
            f"Target={result['target']}, "
            f"Detected={result['detected']}, "
            f"Error={result['difference']:+d}, "
            f"AbsError={result['absolute_error']}"
        )

        summary_lines.append(
            line
        )

        print(
            line
        )

    print()
    print(
        f"Total target       : {total_target}"
    )

    print(
        f"Total detected     : {total_detected}"
    )

    print(
        "Mean absolute error: "
        f"{mean_absolute_error:.3f} blink/round"
    )

    print(
        "Count accuracy     : "
        f"{count_accuracy:.2f}%"
    )

    print(
        f"CSV result         : {csv_path}"
    )

    print(
        f"Screenshot folder  : {screenshot_dir}"
    )

    print(
        f"Summary            : {summary_path}"
    )

    # ========================================================
    # SAVE SUMMARY
    # ========================================================

    with open(
        summary_path,
        "w",
        encoding="utf-8",
    ) as summary_file:

        summary_file.write(
            "PostGuard Blink Detection "
            "Real-Camera Test\n"
        )

        summary_file.write(
            "=" * 60
            +
            "\n\n"
        )

        summary_file.write(
            f"Camera index: "
            f"{CAMERA_INDEX}\n"
        )

        summary_file.write(
            "Requested resolution: "
            f"{REQUESTED_WIDTH}x"
            f"{REQUESTED_HEIGHT}\n"
        )

        summary_file.write(
            "Driver resolution: "
            f"{driver_width}x"
            f"{driver_height}\n"
        )

        summary_file.write(
            f"Driver FPS: "
            f"{driver_fps:.3f}\n\n"
        )

        for line in summary_lines:

            summary_file.write(
                line
                +
                "\n"
            )

        summary_file.write(
            "\n"
        )

        summary_file.write(
            f"Total target: "
            f"{total_target}\n"
        )

        summary_file.write(
            f"Total detected: "
            f"{total_detected}\n"
        )

        summary_file.write(
            "Mean absolute error: "
            f"{mean_absolute_error:.3f} "
            "blink/round\n"
        )

        summary_file.write(
            "Count accuracy: "
            f"{count_accuracy:.2f}%\n"
        )

    print()
    print(
        "TEST COMPLETE"
    )


if __name__ == "__main__":
    main()