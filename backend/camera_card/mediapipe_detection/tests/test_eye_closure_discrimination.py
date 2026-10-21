from pathlib import Path

import sys
import time
import csv
import statistics

from datetime import datetime


import cv2


# ==========================================================
# Project Root
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)


sys.path.insert(
    0,
    str(BASE_DIR)
)


# ==========================================================
# Face Modules
# ==========================================================

from mediapipe_detection.face.face_detector import (
    FaceDetector
)


from mediapipe_detection.face.face_points import (
    extract_face_points
)


# ==========================================================
# Eye Modules
# ==========================================================

from mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness
)


from mediapipe_detection.eye.eye_state import (
    EyeStateDetector,
    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,
    CALIBRATION_READY,
)


from mediapipe_detection.eye.eye_closure import (
    EyeClosureDetector
)


# ==========================================================
# Model
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Eye State Configuration
#
# IMPORTANT:
# ใช้ค่าเดิมที่ผ่าน validation แล้ว
# ห้ามปรับเพื่อให้ diagnostic ผ่าน
# ==========================================================

CALIBRATION_SECONDS = 3.0

MIN_CALIBRATION_SAMPLES = 30

CLOSE_FACTOR = 0.55

REOPEN_FACTOR = 0.70


# ==========================================================
# Current Long Closure Configuration
#
# ยังใช้ค่าปัจจุบัน
# Diagnostic นี้ยังไม่เปลี่ยน threshold
# ==========================================================

LONG_CLOSURE_SECONDS = 1.0


# ==========================================================
# Diagnostic Configuration
# ==========================================================

AUTO_CALIBRATION_DELAY = 2.0

PREPARE_SECONDS = 1.5

CAPTURE_SECONDS = 3.2


# อย่างน้อยต้องจับ action ได้จำนวนนี้
# ไม่งั้นให้ retry round เดิม
MIN_ACTION_FRAMES = 10


# ==========================================================
# Test Sequence
#
# รวมทั้งหมด 9 รอบ
#
# TRUE_LONG_CLOSURE x3
# LEFT_WINK         x3
# RIGHT_WINK        x3
# ==========================================================

TEST_SEQUENCE = []


for round_number in range(
    1,
    4
):

    TEST_SEQUENCE.append(
        {
            "test_type": (
                "TRUE_LONG_CLOSURE"
            ),

            "round": (
                round_number
            ),

            "instruction": (
                "CLOSE BOTH EYES 1.2-1.5 SEC THEN OPEN"
            ),
        }
    )


for round_number in range(
    1,
    4
):

    TEST_SEQUENCE.append(
        {
            "test_type": (
                "LEFT_WINK"
            ),

            "round": (
                round_number
            ),

            "instruction": (
                "CLOSE LEFT EYE ONLY 1.2-1.5 SEC THEN OPEN"
            ),
        }
    )


for round_number in range(
    1,
    4
):

    TEST_SEQUENCE.append(
        {
            "test_type": (
                "RIGHT_WINK"
            ),

            "round": (
                round_number
            ),

            "instruction": (
                "CLOSE RIGHT EYE ONLY 1.2-1.5 SEC THEN OPEN"
            ),
        }
    )


# ==========================================================
# Statistical Helpers
# ==========================================================

def safe_mean(
    values
):

    if not values:

        return None


    return float(
        statistics.mean(
            values
        )
    )


def safe_median(
    values
):

    if not values:

        return None


    return float(
        statistics.median(
            values
        )
    )


def safe_std(
    values
):

    if not values:

        return None


    if len(values) == 1:

        return 0.0


    return float(
        statistics.pstdev(
            values
        )
    )


def safe_min(
    values
):

    if not values:

        return None


    return float(
        min(
            values
        )
    )


def safe_max(
    values
):

    if not values:

        return None


    return float(
        max(
            values
        )
    )


# ==========================================================
# Percentile
# ==========================================================

def percentile(
    values,
    percent
):

    if not values:

        return None


    sorted_values = sorted(
        float(value)
        for value in values
    )


    if len(sorted_values) == 1:

        return (
            sorted_values[0]
        )


    position = (

        (
            len(sorted_values)
            -
            1
        )

        *

        (
            float(percent)
            /
            100.0
        )
    )


    lower_index = int(
        position
    )


    upper_index = min(

        lower_index + 1,

        len(sorted_values) - 1
    )


    fraction = (
        position
        -
        lower_index
    )


    lower_value = (
        sorted_values[
            lower_index
        ]
    )


    upper_value = (
        sorted_values[
            upper_index
        ]
    )


    return float(

        lower_value

        +

        (
            upper_value
            -
            lower_value
        )

        *
        fraction
    )


# ==========================================================
# Format Helper
# ==========================================================

def format_number(
    value,
    digits=4
):

    if value is None:

        return "N/A"


    return (
        f"{value:.{digits}f}"
    )


# ==========================================================
# Detect Action Frame
#
# เราไม่เอาทุก frame ใน capture
# มาคำนวณ summary
#
# เพราะก่อน/หลัง action ผู้ใช้เปิดตาอยู่
#
# TRUE_LONG_CLOSURE
# -> ใช้ frame ที่ BOTH CLOSED
#
# LEFT_WINK
# -> ใช้ frame ที่ LEFT CLOSED
#
# RIGHT_WINK
# -> ใช้ frame ที่ RIGHT CLOSED
# ==========================================================

def is_action_frame(
    test_type,
    right_state,
    left_state
):

    if (
        test_type
        ==
        "TRUE_LONG_CLOSURE"
    ):

        return (

            right_state
            ==
            EYE_CLOSED

            and

            left_state
            ==
            EYE_CLOSED
        )


    if (
        test_type
        ==
        "LEFT_WINK"
    ):

        return (

            left_state
            ==
            EYE_CLOSED
        )


    if (
        test_type
        ==
        "RIGHT_WINK"
    ):

        return (

            right_state
            ==
            EYE_CLOSED
        )


    return False


# ==========================================================
# Summarize One Round
# ==========================================================

def summarize_round(
    rows
):

    valid_rows = [

        row

        for row in rows

        if row[
            "measurement_valid"
        ]
    ]


    action_rows = [

        row

        for row in valid_rows

        if row[
            "is_action_frame"
        ]
    ]


    right_ratios = [

        row[
            "right_ratio"
        ]

        for row in action_rows

        if row[
            "right_ratio"
        ]
        is not None
    ]


    left_ratios = [

        row[
            "left_ratio"
        ]

        for row in action_rows

        if row[
            "left_ratio"
        ]
        is not None
    ]


    ratio_gaps = [

        abs(
            row[
                "right_ratio"
            ]
            -
            row[
                "left_ratio"
            ]
        )

        for row in action_rows

        if (
            row[
                "right_ratio"
            ]
            is not None

            and

            row[
                "left_ratio"
            ]
            is not None
        )
    ]


    right_closed_frames = sum(

        1

        for row in action_rows

        if row[
            "right_state"
        ]
        ==
        EYE_CLOSED
    )


    left_closed_frames = sum(

        1

        for row in action_rows

        if row[
            "left_state"
        ]
        ==
        EYE_CLOSED
    )


    both_closed_frames = sum(

        1

        for row in action_rows

        if (
            row[
                "right_state"
            ]
            ==
            EYE_CLOSED

            and

            row[
                "left_state"
            ]
            ==
            EYE_CLOSED
        )
    )


    action_count = len(
        action_rows
    )


    if action_count > 0:

        right_closed_percent = (

            right_closed_frames
            /
            action_count
            *
            100.0
        )


        left_closed_percent = (

            left_closed_frames
            /
            action_count
            *
            100.0
        )


        both_closed_percent = (

            both_closed_frames
            /
            action_count
            *
            100.0
        )

    else:

        right_closed_percent = 0.0

        left_closed_percent = 0.0

        both_closed_percent = 0.0


    long_closure_events = sum(

        1

        for row in rows

        if row[
            "long_closure_event"
        ]
    )


    closure_durations = [

        row[
            "closure_duration"
        ]

        for row in rows
    ]


    return {

        "valid_frames": (
            len(
                valid_rows
            )
        ),

        "action_frames": (
            action_count
        ),


        # --------------------------------------------------
        # RIGHT Ratio
        # --------------------------------------------------

        "right_ratio_mean": (
            safe_mean(
                right_ratios
            )
        ),

        "right_ratio_median": (
            safe_median(
                right_ratios
            )
        ),

        "right_ratio_std": (
            safe_std(
                right_ratios
            )
        ),

        "right_ratio_min": (
            safe_min(
                right_ratios
            )
        ),

        "right_ratio_p10": (
            percentile(
                right_ratios,
                10
            )
        ),

        "right_ratio_p90": (
            percentile(
                right_ratios,
                90
            )
        ),

        "right_ratio_max": (
            safe_max(
                right_ratios
            )
        ),


        # --------------------------------------------------
        # LEFT Ratio
        # --------------------------------------------------

        "left_ratio_mean": (
            safe_mean(
                left_ratios
            )
        ),

        "left_ratio_median": (
            safe_median(
                left_ratios
            )
        ),

        "left_ratio_std": (
            safe_std(
                left_ratios
            )
        ),

        "left_ratio_min": (
            safe_min(
                left_ratios
            )
        ),

        "left_ratio_p10": (
            percentile(
                left_ratios,
                10
            )
        ),

        "left_ratio_p90": (
            percentile(
                left_ratios,
                90
            )
        ),

        "left_ratio_max": (
            safe_max(
                left_ratios
            )
        ),


        # --------------------------------------------------
        # Gap
        # --------------------------------------------------

        "ratio_gap_mean": (
            safe_mean(
                ratio_gaps
            )
        ),

        "ratio_gap_median": (
            safe_median(
                ratio_gaps
            )
        ),

        "ratio_gap_max": (
            safe_max(
                ratio_gaps
            )
        ),


        # --------------------------------------------------
        # State Distribution
        # --------------------------------------------------

        "right_closed_frames": (
            right_closed_frames
        ),

        "right_closed_percent": (
            right_closed_percent
        ),

        "left_closed_frames": (
            left_closed_frames
        ),

        "left_closed_percent": (
            left_closed_percent
        ),

        "both_closed_frames": (
            both_closed_frames
        ),

        "both_closed_percent": (
            both_closed_percent
        ),


        # --------------------------------------------------
        # Current Long Closure Detector
        # --------------------------------------------------

        "long_closure_events": (
            long_closure_events
        ),

        "max_closure_duration": (
            safe_max(
                closure_durations
            )
        ),
    }


# ==========================================================
# Print One Round
# ==========================================================

def print_round_summary(
    test_type,
    round_number,
    summary
):

    print(
        "\n"
        "########################################################"
    )


    print(
        "EYE CLOSURE DISCRIMINATION ROUND"
    )


    print(
        "########################################################"
    )


    print(
        "TYPE :",
        test_type
    )


    print(
        "ROUND:",
        round_number
    )


    print(
        "--------------------------------------------------------"
    )


    print(
        "Valid Frames :",
        summary[
            "valid_frames"
        ]
    )


    print(
        "Action Frames:",
        summary[
            "action_frames"
        ]
    )


    print(
        "\nRIGHT NORMALIZED OPENNESS"
    )


    print(
        "  Mean   :",
        format_number(
            summary[
                "right_ratio_mean"
            ]
        )
    )


    print(
        "  Median :",
        format_number(
            summary[
                "right_ratio_median"
            ]
        )
    )


    print(
        "  Std    :",
        format_number(
            summary[
                "right_ratio_std"
            ]
        )
    )


    print(
        "  Min    :",
        format_number(
            summary[
                "right_ratio_min"
            ]
        )
    )


    print(
        "  P10    :",
        format_number(
            summary[
                "right_ratio_p10"
            ]
        )
    )


    print(
        "  P90    :",
        format_number(
            summary[
                "right_ratio_p90"
            ]
        )
    )


    print(
        "  Max    :",
        format_number(
            summary[
                "right_ratio_max"
            ]
        )
    )


    print(
        "\nLEFT NORMALIZED OPENNESS"
    )


    print(
        "  Mean   :",
        format_number(
            summary[
                "left_ratio_mean"
            ]
        )
    )


    print(
        "  Median :",
        format_number(
            summary[
                "left_ratio_median"
            ]
        )
    )


    print(
        "  Std    :",
        format_number(
            summary[
                "left_ratio_std"
            ]
        )
    )


    print(
        "  Min    :",
        format_number(
            summary[
                "left_ratio_min"
            ]
        )
    )


    print(
        "  P10    :",
        format_number(
            summary[
                "left_ratio_p10"
            ]
        )
    )


    print(
        "  P90    :",
        format_number(
            summary[
                "left_ratio_p90"
            ]
        )
    )


    print(
        "  Max    :",
        format_number(
            summary[
                "left_ratio_max"
            ]
        )
    )


    print(
        "\nBETWEEN-EYE DIFFERENCE"
    )


    print(
        "  Gap Mean   :",
        format_number(
            summary[
                "ratio_gap_mean"
            ]
        )
    )


    print(
        "  Gap Median :",
        format_number(
            summary[
                "ratio_gap_median"
            ]
        )
    )


    print(
        "  Gap Max    :",
        format_number(
            summary[
                "ratio_gap_max"
            ]
        )
    )


    print(
        "\nSTATE DISTRIBUTION DURING ACTION"
    )


    print(
        "  Right CLOSED:",
        (
            f"{summary['right_closed_frames']} "
            f"({summary['right_closed_percent']:.1f}%)"
        )
    )


    print(
        "  Left CLOSED :",
        (
            f"{summary['left_closed_frames']} "
            f"({summary['left_closed_percent']:.1f}%)"
        )
    )


    print(
        "  Both CLOSED :",
        (
            f"{summary['both_closed_frames']} "
            f"({summary['both_closed_percent']:.1f}%)"
        )
    )


    print(
        "\nCURRENT LONG CLOSURE DETECTOR"
    )


    print(
        "  Events:",
        summary[
            "long_closure_events"
        ]
    )


    print(
        "  Max Duration:",
        (
            format_number(
                summary[
                    "max_closure_duration"
                ],
                3
            )
            +
            " sec"
        )
    )


    print(
        "########################################################"
    )


# ==========================================================
# Save RAW CSV
# ==========================================================

def save_raw_csv(
    rows,
    output_path
):

    fieldnames = [

        "test_type",
        "round",

        "frame_index",
        "elapsed",

        "measurement_valid",

        "right_openness",
        "left_openness",

        "right_open_reference",
        "left_open_reference",

        "right_ratio",
        "left_ratio",

        "right_state",
        "left_state",
        "combined_state",

        "is_action_frame",

        "closure_active",
        "closure_duration",

        "long_closure_event",
        "long_closure_count",

        "closure_reason",
    ]


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(

            file,

            fieldnames=fieldnames
        )


        writer.writeheader()


        for row in rows:

            writer.writerow(
                row
            )


# ==========================================================
# Save Summary CSV
# ==========================================================

def save_summary_csv(
    summaries,
    output_path
):

    if not summaries:

        return


    fieldnames = list(
        summaries[0].keys()
    )


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(

            file,

            fieldnames=fieldnames
        )


        writer.writeheader()


        for row in summaries:

            writer.writerow(
                row
            )


# ==========================================================
# Final Group Summary
# ==========================================================

def print_final_summary(
    all_rows
):

    print(
        "\n\n"
        "========================================================"
    )


    print(
        "POSTGUARD EYE CLOSURE DISCRIMINATION FINAL SUMMARY"
    )


    print(
        "========================================================"
    )


    for test_type in (

        "TRUE_LONG_CLOSURE",
        "LEFT_WINK",
        "RIGHT_WINK",

    ):

        action_rows = [

            row

            for row in all_rows

            if (
                row[
                    "test_type"
                ]
                ==
                test_type

                and

                row[
                    "measurement_valid"
                ]

                and

                row[
                    "is_action_frame"
                ]
            )
        ]


        right_ratios = [

            row[
                "right_ratio"
            ]

            for row in action_rows

            if row[
                "right_ratio"
            ]
            is not None
        ]


        left_ratios = [

            row[
                "left_ratio"
            ]

            for row in action_rows

            if row[
                "left_ratio"
            ]
            is not None
        ]


        gaps = [

            abs(
                row[
                    "right_ratio"
                ]
                -
                row[
                    "left_ratio"
                ]
            )

            for row in action_rows

            if (
                row[
                    "right_ratio"
                ]
                is not None

                and

                row[
                    "left_ratio"
                ]
                is not None
            )
        ]


        both_closed = sum(

            1

            for row in action_rows

            if (
                row[
                    "right_state"
                ]
                ==
                EYE_CLOSED

                and

                row[
                    "left_state"
                ]
                ==
                EYE_CLOSED
            )
        )


        if action_rows:

            both_closed_percent = (

                both_closed
                /
                len(
                    action_rows
                )
                *
                100.0
            )

        else:

            both_closed_percent = (
                0.0
            )


        event_count = sum(

            1

            for row in all_rows

            if (
                row[
                    "test_type"
                ]
                ==
                test_type

                and

                row[
                    "long_closure_event"
                ]
            )
        )


        print(
            "\n"
            "--------------------------------------------------------"
        )


        print(
            test_type
        )


        print(
            "--------------------------------------------------------"
        )


        print(
            "Action Frames:",
            len(
                action_rows
            )
        )


        print(
            "RIGHT Ratio Median:",
            format_number(
                safe_median(
                    right_ratios
                )
            )
        )


        print(
            "RIGHT Ratio P10:",
            format_number(
                percentile(
                    right_ratios,
                    10
                )
            )
        )


        print(
            "RIGHT Ratio P90:",
            format_number(
                percentile(
                    right_ratios,
                    90
                )
            )
        )


        print(
            "LEFT Ratio Median:",
            format_number(
                safe_median(
                    left_ratios
                )
            )
        )


        print(
            "LEFT Ratio P10:",
            format_number(
                percentile(
                    left_ratios,
                    10
                )
            )
        )


        print(
            "LEFT Ratio P90:",
            format_number(
                percentile(
                    left_ratios,
                    90
                )
            )
        )


        print(
            "Ratio Gap Median:",
            format_number(
                safe_median(
                    gaps
                )
            )
        )


        print(
            "Both CLOSED:",
            (
                f"{both_closed}/"
                f"{len(action_rows)} "
                f"({both_closed_percent:.1f}%)"
            )
        )


        print(
            "Long Closure Events:",
            event_count
        )


    print(
        "\n"
        "========================================================"
    )


    print(
        "DIAGNOSTIC COMPLETE"
    )


    print(
        "Do NOT change thresholds yet."
    )


    print(
        "========================================================"
    )


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # Model Check
    # ======================================================

    if not FACE_MODEL_PATH.exists():

        print(
            "Face model not found:"
        )


        print(
            FACE_MODEL_PATH
        )


        return


    # ======================================================
    # Create Detectors
    # ======================================================

    face_detector = (
        FaceDetector(
            FACE_MODEL_PATH
        )
    )


    eye_state_detector = (
        EyeStateDetector(

            calibration_seconds=(
                CALIBRATION_SECONDS
            ),

            min_calibration_samples=(
                MIN_CALIBRATION_SAMPLES
            ),

            close_factor=(
                CLOSE_FACTOR
            ),

            reopen_factor=(
                REOPEN_FACTOR
            ),
        )
    )


    closure_detector = (
        EyeClosureDetector(

            long_closure_seconds=(
                LONG_CLOSURE_SECONDS
            )
        )
    )


    # ======================================================
    # Camera
    # ======================================================

    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        print(
            "Cannot open camera."
        )


        face_detector.close()


        return


    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )


    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )


    # ======================================================
    # Output Folder
    # ======================================================

    output_dir = (

        BASE_DIR
        /
        "mediapipe_detection"
        /
        "tests"
        /
        "results"
    )


    output_dir.mkdir(

        parents=True,

        exist_ok=True
    )


    file_timestamp = (

        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )


    raw_output_path = (

        output_dir

        /

        (
            "eye_closure_discrimination_raw_"
            +
            file_timestamp
            +
            ".csv"
        )
    )


    summary_output_path = (

        output_dir

        /

        (
            "eye_closure_discrimination_summary_"
            +
            file_timestamp
            +
            ".csv"
        )
    )


    # ======================================================
    # Runtime Variables
    # ======================================================

    program_started_at = (
        time.perf_counter()
    )


    auto_calibration_started = False

    calibration_printed = False


    right_open_reference = None

    left_open_reference = None


    test_index = 0


    preparing = False

    collecting = False


    prepare_started_at = None

    capture_started_at = None


    current_rows = []

    all_rows = []

    summaries = []


    frame_index = 0


    diagnostic_complete = False


    status_message = (
        "Preparing automatic calibration..."
    )


    # ======================================================
    # Instructions
    # ======================================================

    print(
        "\n"
        "========================================================\n"
        "POSTGUARD EYE CLOSURE DISCRIMINATION DIAGNOSTIC\n"
        "========================================================\n"
        "\n"
        "Tests:\n"
        "TRUE_LONG_CLOSURE x3\n"
        "LEFT_WINK         x3\n"
        "RIGHT_WINK        x3\n"
        "\n"
        "Sit in your NATURAL working position.\n"
        "Do NOT move closer to the camera.\n"
        "\n"
        "Calibration starts automatically.\n"
        "\n"
        "SPACE = start round\n"
        "R     = reset all\n"
        "Q/ESC = quit\n"
        "========================================================\n"
    )


    # ======================================================
    # Main Camera Loop
    # ======================================================

    while True:

        ret, raw_frame = (
            cap.read()
        )


        if not ret:

            print(
                "Cannot read camera frame."
            )

            break


        frame_height, frame_width = (
            raw_frame.shape[:2]
        )


        now = (
            time.perf_counter()
        )


        # ==================================================
        # Face Detection
        # ==================================================

        face_result = (
            face_detector.detect(
                raw_frame
            )
        )


        face_points = (
            extract_face_points(

                face_result,

                frame_width,

                frame_height
            )
        )


        # ==================================================
        # Eye Measurement
        # ==================================================

        eye_measurement = (
            calculate_eye_openness(
                face_points
            )
        )


        measurement_valid = (

            eye_measurement
            is not None
        )


        # ==================================================
        # Auto Calibration
        # ==================================================

        if (
            not auto_calibration_started

            and

            measurement_valid

            and

            (
                now
                -
                program_started_at
            )
            >=
            AUTO_CALIBRATION_DELAY
        ):

            eye_state_detector.start_calibration(
                timestamp=now
            )


            closure_detector.reset()


            auto_calibration_started = True


            status_message = (
                "CALIBRATING - KEEP BOTH EYES OPEN"
            )


            print(
                "\nCalibration started automatically."
            )


            print(
                "Keep BOTH eyes naturally OPEN."
            )


        # ==================================================
        # Eye State
        # ==================================================

        eye_state_result = (
            eye_state_detector.update(

                eye_measurement,

                timestamp=now
            )
        )


        # ==================================================
        # Current Long Closure Detector
        # ==================================================

        closure_result = (
            closure_detector.update(

                eye_state_result,

                timestamp=now
            )
        )


        # ==================================================
        # Calibration Ready
        # ==================================================

        if (
            eye_state_result[
                "calibration_status"
            ]
            ==
            CALIBRATION_READY

            and

            not calibration_printed
        ):

            calibration_printed = True


            right_open_reference = float(

                eye_state_result[
                    "right_open_reference"
                ]
            )


            left_open_reference = float(

                eye_state_result[
                    "left_open_reference"
                ]
            )


            closure_detector.reset()


            status_message = (
                "READY - Press SPACE"
            )


            print(
                "\n"
                "=============================================="
            )


            print(
                "CALIBRATION READY"
            )


            print(
                "=============================================="
            )


            print(
                "RIGHT Reference:",
                f"{right_open_reference:.5f}"
            )


            print(
                "RIGHT Close:",
                f"{eye_state_result['right_close_threshold']:.5f}"
            )


            print(
                "RIGHT Reopen:",
                f"{eye_state_result['right_reopen_threshold']:.5f}"
            )


            print(
                "\nLEFT Reference:",
                f"{left_open_reference:.5f}"
            )


            print(
                "LEFT Close:",
                f"{eye_state_result['left_close_threshold']:.5f}"
            )


            print(
                "LEFT Reopen:",
                f"{eye_state_result['left_reopen_threshold']:.5f}"
            )


            print(
                "=============================================="
            )


        # ==================================================
        # PREPARE
        # ==================================================

        if preparing:

            prepare_elapsed = (
                now
                -
                prepare_started_at
            )


            if (
                prepare_elapsed
                >=
                PREPARE_SECONDS
            ):

                preparing = False

                collecting = True


                capture_started_at = (
                    now
                )


                current_rows = []

                frame_index = 0


                current_test = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print(
                    "\n"
                    "=============================================="
                )


                print(
                    "CAPTURE STARTED"
                )


                print(
                    "TYPE:",
                    current_test[
                        "test_type"
                    ]
                )


                print(
                    "ROUND:",
                    current_test[
                        "round"
                    ]
                )


                print(
                    current_test[
                        "instruction"
                    ]
                )


                print(
                    "=============================================="
                )


        # ==================================================
        # CAPTURE
        # ==================================================

        if collecting:

            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            capture_elapsed = (
                now
                -
                capture_started_at
            )


            frame_index += 1


            # ==============================================
            # Current Values
            # ==============================================

            right_openness = None

            left_openness = None

            right_ratio = None

            left_ratio = None


            if (
                measurement_valid

                and

                right_open_reference
                is not None

                and

                left_open_reference
                is not None

                and

                right_open_reference
                >
                0

                and

                left_open_reference
                >
                0
            ):

                right_openness = float(

                    eye_measurement[
                        "right_eye_openness"
                    ]
                )


                left_openness = float(

                    eye_measurement[
                        "left_eye_openness"
                    ]
                )


                # ==========================================
                # Normalized Openness
                #
                # current / personal open reference
                # ==========================================

                right_ratio = (

                    right_openness
                    /
                    right_open_reference
                )


                left_ratio = (

                    left_openness
                    /
                    left_open_reference
                )


            # ==============================================
            # States
            # ==============================================

            right_state = (
                eye_state_result.get(
                    "right_eye_state",
                    EYE_UNKNOWN
                )
            )


            left_state = (
                eye_state_result.get(
                    "left_eye_state",
                    EYE_UNKNOWN
                )
            )


            combined_state = (
                eye_state_result.get(
                    "eye_state",
                    EYE_UNKNOWN
                )
            )


            action_frame = (
                is_action_frame(

                    current_test[
                        "test_type"
                    ],

                    right_state,

                    left_state
                )
            )


            # ==============================================
            # Save Frame
            # ==============================================

            current_rows.append(
                {
                    "test_type": (
                        current_test[
                            "test_type"
                        ]
                    ),

                    "round": (
                        current_test[
                            "round"
                        ]
                    ),

                    "frame_index": (
                        frame_index
                    ),

                    "elapsed": (
                        float(
                            capture_elapsed
                        )
                    ),

                    "measurement_valid": (
                        bool(
                            measurement_valid
                        )
                    ),

                    "right_openness": (
                        right_openness
                    ),

                    "left_openness": (
                        left_openness
                    ),

                    "right_open_reference": (
                        right_open_reference
                    ),

                    "left_open_reference": (
                        left_open_reference
                    ),

                    "right_ratio": (
                        right_ratio
                    ),

                    "left_ratio": (
                        left_ratio
                    ),

                    "right_state": (
                        right_state
                    ),

                    "left_state": (
                        left_state
                    ),

                    "combined_state": (
                        combined_state
                    ),

                    "is_action_frame": (
                        bool(
                            action_frame
                        )
                    ),

                    "closure_active": (
                        bool(
                            closure_result[
                                "eye_closure_active"
                            ]
                        )
                    ),

                    "closure_duration": (
                        float(
                            closure_result[
                                "eye_closure_duration"
                            ]
                        )
                    ),

                    "long_closure_event": (
                        bool(
                            closure_result[
                                "long_closure_event"
                            ]
                        )
                    ),

                    "long_closure_count": (
                        int(
                            closure_result[
                                "long_closure_count"
                            ]
                        )
                    ),

                    "closure_reason": (
                        closure_result[
                            "reason"
                        ]
                    ),
                }
            )


            # ==============================================
            # Show Current Event
            # ==============================================

            if closure_result[
                "long_closure_event"
            ]:

                print(
                    "LONG CLOSURE EVENT",
                    f"duration="
                    f"{closure_result['eye_closure_duration']:.3f}s"
                )


            # ==============================================
            # Capture Finished
            # ==============================================

            if (
                capture_elapsed
                >=
                CAPTURE_SECONDS
            ):

                collecting = False


                summary = (
                    summarize_round(
                        current_rows
                    )
                )


                # ==========================================
                # Data Quality Check
                # ==========================================

                if (
                    summary[
                        "action_frames"
                    ]
                    <
                    MIN_ACTION_FRAMES
                ):

                    print(
                        "\n"
                        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    )


                    print(
                        "ROUND NEEDS RETRY"
                    )


                    print(
                        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
                    )


                    print(
                        "Action Frames:",
                        summary[
                            "action_frames"
                        ]
                    )


                    print(
                        "Required >=",
                        MIN_ACTION_FRAMES
                    )


                    print(
                        "Press SPACE to retry SAME round."
                    )


                    status_message = (
                        "RETRY SAME ROUND - Press SPACE"
                    )


                    current_rows = []


                else:

                    # ======================================
                    # Accept Round
                    # ======================================

                    all_rows.extend(
                        current_rows
                    )


                    summary_row = {
                        "test_type": (
                            current_test[
                                "test_type"
                            ]
                        ),

                        "round": (
                            current_test[
                                "round"
                            ]
                        ),

                        **summary,
                    }


                    summaries.append(
                        summary_row
                    )


                    print_round_summary(

                        current_test[
                            "test_type"
                        ],

                        current_test[
                            "round"
                        ],

                        summary
                    )


                    # ======================================
                    # Next Round
                    # ======================================

                    test_index += 1


                    if (
                        test_index
                        >=
                        len(
                            TEST_SEQUENCE
                        )
                    ):

                        diagnostic_complete = (
                            True
                        )


                        save_raw_csv(
                            all_rows,
                            raw_output_path
                        )


                        save_summary_csv(
                            summaries,
                            summary_output_path
                        )


                        print_final_summary(
                            all_rows
                        )


                        print(
                            "\nRAW CSV:"
                        )


                        print(
                            raw_output_path
                        )


                        print(
                            "\nSUMMARY CSV:"
                        )


                        print(
                            summary_output_path
                        )


                        status_message = (
                            "DIAGNOSTIC COMPLETE"
                        )


                    else:

                        next_test = (
                            TEST_SEQUENCE[
                                test_index
                            ]
                        )


                        status_message = (

                            "NEXT: "

                            +

                            next_test[
                                "test_type"
                            ]

                            +

                            " ROUND "

                            +

                            str(
                                next_test[
                                    "round"
                                ]
                            )

                            +

                            " - Press SPACE"
                        )


                        print(
                            "\nNext:"
                        )


                        print(
                            next_test[
                                "test_type"
                            ],
                            "Round",
                            next_test[
                                "round"
                            ]
                        )


                        print(
                            next_test[
                                "instruction"
                            ]
                        )


                        print(
                            "Press SPACE when ready."
                        )


        # ==================================================
        # Display
        # ==================================================

        display_frame = (
            cv2.flip(
                raw_frame,
                1
            )
        )


        # ==================================================
        # Current Test
        # ==================================================

        if (
            not diagnostic_complete

            and

            test_index
            <
            len(
                TEST_SEQUENCE
            )
        ):

            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            test_text = (

                current_test[
                    "test_type"
                ]

                +

                " ROUND "

                +

                str(
                    current_test[
                        "round"
                    ]
                )
            )


            instruction_text = (
                current_test[
                    "instruction"
                ]
            )


        else:

            test_text = (
                "COMPLETE"
            )


            instruction_text = (
                "DIAGNOSTIC COMPLETE"
            )


        # ==================================================
        # Current Ratio for Screen
        # ==================================================

        if (
            eye_measurement
            is not None

            and

            right_open_reference
            is not None

            and

            left_open_reference
            is not None

            and

            right_open_reference
            >
            0

            and

            left_open_reference
            >
            0
        ):

            screen_right = float(

                eye_measurement[
                    "right_eye_openness"
                ]
            )


            screen_left = float(

                eye_measurement[
                    "left_eye_openness"
                ]
            )


            screen_right_ratio = (

                screen_right
                /
                right_open_reference
            )


            screen_left_ratio = (

                screen_left
                /
                left_open_reference
            )


            cv2.putText(
                display_frame,
                (
                    "R Openness: "
                    f"{screen_right:.3f}"
                ),
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


            cv2.putText(
                display_frame,
                (
                    "L Openness: "
                    f"{screen_left:.3f}"
                ),
                (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


            cv2.putText(
                display_frame,
                (
                    "R Ratio: "
                    f"{screen_right_ratio:.3f}"
                ),
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "L Ratio: "
                    f"{screen_left_ratio:.3f}"
                ),
                (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Eye Measurement: UNKNOWN",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 255),
                2
            )


        # ==================================================
        # States
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "R State: "
                +
                str(
                    eye_state_result.get(
                        "right_eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 185),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "L State: "
                +
                str(
                    eye_state_result.get(
                        "left_eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 215),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            (
                "Combined: "
                +
                str(
                    eye_state_result.get(
                        "eye_state",
                        EYE_UNKNOWN
                    )
                )
            ),
            (20, 245),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Long Closure Runtime
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "Closure Duration: "
                f"{closure_result['eye_closure_duration']:.2f}s"
            ),
            (20, 285),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            (
                "Closure Reason: "
                +
                str(
                    closure_result[
                        "reason"
                    ]
                )
            ),
            (20, 315),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Test
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "TEST: "
                +
                test_text
            ),
            (20, 365),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            instruction_text,
            (20, 395),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Runtime Status
        # ==================================================

        if preparing:

            remaining = max(

                0.0,

                PREPARE_SECONDS
                -
                (
                    now
                    -
                    prepare_started_at
                )
            )


            runtime_text = (

                "PREPARE - BOTH EYES OPEN "

                f"{remaining:.1f}s"
            )


        elif collecting:

            capture_elapsed = (

                now
                -
                capture_started_at
            )


            runtime_text = (

                "CAPTURE "

                f"{capture_elapsed:.1f}/"

                f"{CAPTURE_SECONDS:.1f}s"
            )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            runtime_text,
            (20, 435),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            "SPACE=Start  R=Reset  Q=Quit",
            (
                20,
                frame_height - 25
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1
        )


        cv2.imshow(
            "PostGuard - Eye Closure Discrimination",
            display_frame
        )


        # ==================================================
        # Keyboard
        # ==================================================

        key = (
            cv2.waitKey(1)
            &
            0xFF
        )


        # ==================================================
        # Quit
        # ==================================================

        if key in (
            ord("q"),
            ord("Q"),
            27
        ):

            break


        # ==================================================
        # SPACE
        # ==================================================

        if (
            key
            ==
            ord(" ")

            and

            eye_state_result.get(
                "calibrated",
                False
            )

            and

            not diagnostic_complete

            and

            not preparing

            and

            not collecting
        ):

            # ==============================================
            # Reset Long Closure before each round
            # ==============================================

            closure_detector.reset()


            # ==============================================
            # Begin PREPARE
            # ==============================================

            preparing = True


            prepare_started_at = (
                now
            )


            current_rows = []


            current_test = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            status_message = (

                "PREPARING "

                +

                current_test[
                    "test_type"
                ]
            )


            print(
                "\nPrepare:"
            )


            print(
                current_test[
                    "test_type"
                ],
                "Round",
                current_test[
                    "round"
                ]
            )


            print(
                "KEEP BOTH EYES NATURALLY OPEN."
            )


            print(
                "When CAPTURE starts:"
            )


            print(
                current_test[
                    "instruction"
                ]
            )


        # ==================================================
        # Reset All
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            eye_state_detector.reset()

            closure_detector.reset()


            program_started_at = (
                time.perf_counter()
            )


            auto_calibration_started = False

            calibration_printed = False


            right_open_reference = None

            left_open_reference = None


            test_index = 0


            preparing = False

            collecting = False


            prepare_started_at = None

            capture_started_at = None


            current_rows = []

            all_rows = []

            summaries = []


            frame_index = 0


            diagnostic_complete = False


            status_message = (
                "RESET - Preparing automatic calibration..."
            )


            print(
                "\nDiagnostic RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()

    face_detector.close()

    cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()