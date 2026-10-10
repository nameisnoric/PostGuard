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
# Face
# ==========================================================

from mediapipe_detection.face.face_detector import (
    FaceDetector
)

from mediapipe_detection.face.face_points import (
    extract_face_points
)


# ==========================================================
# Eye Measurement
# ==========================================================

from mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness
)


# ==========================================================
# Eye State
# ==========================================================

from mediapipe_detection.eye.eye_state import (
    EyeStateDetector,

    EYE_OPEN,
    EYE_CLOSED,
    EYE_UNKNOWN,

    CALIBRATION_READY,
)


# ==========================================================
# Current Blink Detector
#
# IMPORTANT:
#
# Diagnostic นี้ยังไม่แก้ BlinkDetector
# เราแค่เก็บผลของ detector ปัจจุบัน
# ==========================================================

from mediapipe_detection.eye.blink_detector import (
    BlinkDetector
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
# Existing Eye State Configuration
#
# ค่าเดิมที่เราใช้และ LOCK แล้ว
# ห้ามปรับเพื่อให้ test ผ่าน
# ==========================================================

CALIBRATION_SECONDS = 3.0

MIN_CALIBRATION_SAMPLES = 30

CLOSE_FACTOR = 0.55

REOPEN_FACTOR = 0.70


# ==========================================================
# Existing Blink Configuration
#
# ตอนนี้ยังไม่แก้
# ==========================================================

MIN_BLINK_SECONDS = 0.05

MAX_BLINK_SECONDS = 0.80

MAX_CLOSE_SYNC_SECONDS = 0.12


# ==========================================================
# Event-Centered Diagnostic Configuration
#
# ค่าพวกนี้ใช้แบ่งขอบเขตของ test event เท่านั้น
#
# ไม่ใช่ Blink threshold ใหม่
# ==========================================================

AUTO_CALIBRATION_DELAY = 2.0

PREPARE_SECONDS = 1.5


# ==========================================================
# หลังขึ้น WAITING FOR ACTION
#
# ถ้าไม่มี OPEN -> CLOSED ภายใน 4 วินาที
# ให้ retry รอบเดิม
# ==========================================================

WAIT_ACTION_TIMEOUT = 4.0


# ==========================================================
# Action หนึ่งครั้งให้ยาวได้สูงสุด 2.5 วินาที
#
# ถ้ายังไม่กลับ OPEN
# ถือว่า event ไม่สมบูรณ์
# ==========================================================

MAX_EVENT_SECONDS = 2.5


# ==========================================================
# หลังกลับ OPEN ทั้งสองตา
#
# ต้อง OPEN ต่อเนื่อง 0.15 วินาที
# จึงถือว่า event จบ
#
# ป้องกัน noise 1 frame
# ==========================================================

RETURN_OPEN_STABLE_SECONDS = 0.15


# ==========================================================
# จำนวน Frame ขั้นต่ำของ Event
# ==========================================================

MIN_EVENT_FRAMES = 2


# ==========================================================
# Test Sequence
#
# 1 Physical Action = 1 Event
# ==========================================================

TEST_SEQUENCE = []


# ==========================================================
# TRUE BLINK × 5
# ==========================================================

for round_number in range(
    1,
    6
):

    TEST_SEQUENCE.append(
        {
            "test_type": (
                "TRUE_BLINK"
            ),

            "round": (
                round_number
            ),

            "instruction": (
                "BLINK NATURALLY EXACTLY ONCE"
            ),
        }
    )


# ==========================================================
# LEFT WINK × 3
# ==========================================================

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
                "CLOSE LEFT EYE ONLY FOR "
                "0.8-1.2 SEC THEN OPEN"
            ),
        }
    )


# ==========================================================
# RIGHT WINK × 3
# ==========================================================

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
                "CLOSE RIGHT EYE ONLY FOR "
                "0.8-1.2 SEC THEN OPEN"
            ),
        }
    )


# ==========================================================
# Numeric Helpers
# ==========================================================

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


# ==========================================================
# Format Number
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
# Calculate Normalized Eye Ratios
#
# normalized ratio =
#
# current openness
# ----------------
# open reference
#
#
# OPEN:
# ratio ประมาณ 1
#
# CLOSED:
# ratio ลดลง
# ==========================================================

def calculate_normalized_ratios(
    eye_measurement,
    right_reference,
    left_reference
):

    # ------------------------------------------------------
    # Measurement Missing
    # ------------------------------------------------------

    if eye_measurement is None:

        return (
            None,
            None
        )


    # ------------------------------------------------------
    # Reference Missing
    # ------------------------------------------------------

    if (
        right_reference is None

        or

        left_reference is None
    ):

        return (
            None,
            None
        )


    # ------------------------------------------------------
    # Invalid Reference
    # ------------------------------------------------------

    if (
        right_reference <= 0

        or

        left_reference <= 0
    ):

        return (
            None,
            None
        )


    # ------------------------------------------------------
    # Current Eye Openness
    # ------------------------------------------------------

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


    # ------------------------------------------------------
    # Normalize
    # ------------------------------------------------------

    right_ratio = (

        right_openness
        /
        right_reference
    )


    left_ratio = (

        left_openness
        /
        left_reference
    )


    return (
        float(
            right_ratio
        ),

        float(
            left_ratio
        ),
    )


# ==========================================================
# Longest State Duration
#
# เช่น:
#
# RIGHT CLOSED ต่อเนื่องนานที่สุดเท่าไร
# ==========================================================

def longest_state_duration(
    rows,
    state_key,
    target_state
):

    if not rows:

        return 0.0


    longest = 0.0

    current_start = None


    for row in rows:

        timestamp = (
            row[
                "event_elapsed"
            ]
        )


        state = (
            row[
                state_key
            ]
        )


        if state == target_state:

            if current_start is None:

                current_start = (
                    timestamp
                )


        else:

            if current_start is not None:

                duration = (

                    timestamp
                    -
                    current_start
                )


                longest = max(

                    longest,

                    duration
                )


                current_start = None


    # ------------------------------------------------------
    # Event จบตอนยังอยู่ state เดิม
    # ------------------------------------------------------

    if current_start is not None:

        duration = (

            rows[-1][
                "event_elapsed"
            ]

            -

            current_start
        )


        longest = max(

            longest,

            duration
        )


    return float(
        longest
    )


# ==========================================================
# Longest Both CLOSED Duration
# ==========================================================

def longest_both_closed_duration(
    rows
):

    if not rows:

        return 0.0


    longest = 0.0

    current_start = None


    for row in rows:

        timestamp = (
            row[
                "event_elapsed"
            ]
        )


        both_closed = (

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


        if both_closed:

            if current_start is None:

                current_start = (
                    timestamp
                )


        else:

            if current_start is not None:

                duration = (

                    timestamp
                    -
                    current_start
                )


                longest = max(

                    longest,

                    duration
                )


                current_start = None


    if current_start is not None:

        duration = (

            rows[-1][
                "event_elapsed"
            ]

            -

            current_start
        )


        longest = max(

            longest,

            duration
        )


    return float(
        longest
    )


# ==========================================================
# First Time State Appears
#
# เช่น:
#
# หาเวลาที่ RIGHT เข้า CLOSED ครั้งแรก
# ==========================================================

def first_state_time(
    rows,
    state_key,
    target_state
):

    for row in rows:

        if (
            row[
                state_key
            ]
            ==
            target_state
        ):

            return float(
                row[
                    "event_elapsed"
                ]
            )


    return None


# ==========================================================
# First Reopen Time
#
# CLOSED
#   ↓
# OPEN
#
# หา OPEN ครั้งแรกหลังจากเคย CLOSED
# ==========================================================

def first_reopen_time(
    rows,
    state_key
):

    closed_seen = False


    for row in rows:

        state = (
            row[
                state_key
            ]
        )


        if state == EYE_CLOSED:

            closed_seen = True


        elif (
            closed_seen

            and

            state == EYE_OPEN
        ):

            return float(
                row[
                    "event_elapsed"
                ]
            )


    return None


# ==========================================================
# Analyze One Physical Event
# ==========================================================

def analyze_event(
    event_rows
):

    # ======================================================
    # Valid Ratio Rows
    # ======================================================

    valid_rows = [

        row

        for row in event_rows

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


    # ======================================================
    # Per-eye Ratios
    # ======================================================

    right_ratios = [

        row[
            "right_ratio"
        ]

        for row in valid_rows
    ]


    left_ratios = [

        row[
            "left_ratio"
        ]

        for row in valid_rows
    ]


    # ======================================================
    # Bilateral Max
    #
    # max(R, L)
    #
    # ถ้าค่านี้ต่ำ:
    # แปลว่าตาทั้งสองข้างต่ำพร้อมกัน
    # ======================================================

    bilateral_max_values = [

        max(

            row[
                "right_ratio"
            ],

            row[
                "left_ratio"
            ]
        )

        for row in valid_rows
    ]


    # ======================================================
    # Bilateral Min
    # ======================================================

    bilateral_min_values = [

        min(

            row[
                "right_ratio"
            ],

            row[
                "left_ratio"
            ]
        )

        for row in valid_rows
    ]


    # ======================================================
    # Eye Difference
    # ======================================================

    gap_values = [

        abs(

            row[
                "right_ratio"
            ]

            -

            row[
                "left_ratio"
            ]
        )

        for row in valid_rows
    ]


    # ======================================================
    # Deepest Bilateral Moment
    #
    # หา frame ที่ max(R,L) ต่ำที่สุด
    #
    # คือช่วงที่สองตาปิดพร้อมกันลึกที่สุด
    # ======================================================

    deepest_row = None


    if valid_rows:

        deepest_row = min(

            valid_rows,

            key=lambda row: max(

                row[
                    "right_ratio"
                ],

                row[
                    "left_ratio"
                ]
            )
        )


    if deepest_row is None:

        deepest_time = None

        deepest_right_ratio = None

        deepest_left_ratio = None

        deepest_bilateral_max = None

        deepest_gap = None


    else:

        deepest_time = (
            deepest_row[
                "event_elapsed"
            ]
        )


        deepest_right_ratio = (
            deepest_row[
                "right_ratio"
            ]
        )


        deepest_left_ratio = (
            deepest_row[
                "left_ratio"
            ]
        )


        deepest_bilateral_max = max(

            deepest_right_ratio,

            deepest_left_ratio
        )


        deepest_gap = abs(

            deepest_right_ratio

            -

            deepest_left_ratio
        )


    # ======================================================
    # Close Timing
    # ======================================================

    right_close_time = (
        first_state_time(

            event_rows,

            "right_state",

            EYE_CLOSED
        )
    )


    left_close_time = (
        first_state_time(

            event_rows,

            "left_state",

            EYE_CLOSED
        )
    )


    if (
        right_close_time is not None

        and

        left_close_time is not None
    ):

        close_sync = abs(

            right_close_time

            -

            left_close_time
        )


    else:

        close_sync = None


    # ======================================================
    # Reopen Timing
    # ======================================================

    right_reopen_time = (
        first_reopen_time(

            event_rows,

            "right_state"
        )
    )


    left_reopen_time = (
        first_reopen_time(

            event_rows,

            "left_state"
        )
    )


    if (
        right_reopen_time is not None

        and

        left_reopen_time is not None
    ):

        reopen_sync = abs(

            right_reopen_time

            -

            left_reopen_time
        )


    else:

        reopen_sync = None


    # ======================================================
    # CLOSED Duration
    # ======================================================

    right_closed_duration = (
        longest_state_duration(

            event_rows,

            "right_state",

            EYE_CLOSED
        )
    )


    left_closed_duration = (
        longest_state_duration(

            event_rows,

            "left_state",

            EYE_CLOSED
        )
    )


    both_closed_duration = (
        longest_both_closed_duration(
            event_rows
        )
    )


    # ======================================================
    # Duration Difference
    #
    # Blink จริง:
    # คาดว่า R/L duration ใกล้กัน
    #
    # Wink:
    # อาจต่างกันมากกว่า
    #
    # ยังเป็น diagnostic เท่านั้น
    # ======================================================

    closed_duration_gap = abs(

        right_closed_duration

        -

        left_closed_duration
    )


    # ======================================================
    # Existing Blink Detector Output
    # ======================================================

    blink_event_rows = [

        row

        for row in event_rows

        if row[
            "blink_event"
        ]
    ]


    blink_durations = [

        row[
            "blink_duration"
        ]

        for row in blink_event_rows

        if row[
            "blink_duration"
        ]
        is not None
    ]


    blink_event_count = len(
        blink_event_rows
    )


    # ======================================================
    # Event Duration
    # ======================================================

    if event_rows:

        event_duration = (

            event_rows[-1][
                "event_elapsed"
            ]

            -

            event_rows[0][
                "event_elapsed"
            ]
        )


    else:

        event_duration = 0.0


    # ======================================================
    # Return
    # ======================================================

    return {

        # --------------------------------------------------
        # Frame Counts
        # --------------------------------------------------

        "event_frames": (
            len(
                event_rows
            )
        ),

        "valid_frames": (
            len(
                valid_rows
            )
        ),


        # --------------------------------------------------
        # Per-eye Depth
        # --------------------------------------------------

        "right_ratio_min": (
            safe_min(
                right_ratios
            )
        ),

        "left_ratio_min": (
            safe_min(
                left_ratios
            )
        ),

        "right_ratio_median": (
            safe_median(
                right_ratios
            )
        ),

        "left_ratio_median": (
            safe_median(
                left_ratios
            )
        ),


        # --------------------------------------------------
        # Bilateral Depth
        # --------------------------------------------------

        "bilateral_max_min": (
            safe_min(
                bilateral_max_values
            )
        ),

        "bilateral_max_median": (
            safe_median(
                bilateral_max_values
            )
        ),

        "bilateral_min_min": (
            safe_min(
                bilateral_min_values
            )
        ),

        "gap_median": (
            safe_median(
                gap_values
            )
        ),


        # --------------------------------------------------
        # Deepest Bilateral Moment
        # --------------------------------------------------

        "deepest_time": (
            deepest_time
        ),

        "deepest_right_ratio": (
            deepest_right_ratio
        ),

        "deepest_left_ratio": (
            deepest_left_ratio
        ),

        "deepest_bilateral_max": (
            deepest_bilateral_max
        ),

        "deepest_gap": (
            deepest_gap
        ),


        # --------------------------------------------------
        # Close Timing
        # --------------------------------------------------

        "right_close_time": (
            right_close_time
        ),

        "left_close_time": (
            left_close_time
        ),

        "close_sync_seconds": (
            close_sync
        ),


        # --------------------------------------------------
        # Reopen Timing
        # --------------------------------------------------

        "right_reopen_time": (
            right_reopen_time
        ),

        "left_reopen_time": (
            left_reopen_time
        ),

        "reopen_sync_seconds": (
            reopen_sync
        ),


        # --------------------------------------------------
        # Closed Duration
        # --------------------------------------------------

        "right_closed_duration": (
            right_closed_duration
        ),

        "left_closed_duration": (
            left_closed_duration
        ),

        "both_closed_duration": (
            both_closed_duration
        ),

        "closed_duration_gap": (
            closed_duration_gap
        ),


        # --------------------------------------------------
        # Whole Event
        # --------------------------------------------------

        "event_duration": (
            event_duration
        ),


        # --------------------------------------------------
        # Current Blink Detector
        # --------------------------------------------------

        "blink_event_count": (
            blink_event_count
        ),

        "blink_duration_max": (
            safe_max(
                blink_durations
            )
        ),
    }


# ==========================================================
# Print One Event Summary
# ==========================================================

def print_event_summary(
    test_type,
    round_number,
    summary
):

    print(
        "\n"
        "########################################################"
    )


    print(
        "POSTGUARD EVENT-CENTERED BLINK DIAGNOSTIC"
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
        "Event Frames:",
        summary[
            "event_frames"
        ]
    )


    print(
        "Valid Frames:",
        summary[
            "valid_frames"
        ]
    )


    # ======================================================
    # Depth
    # ======================================================

    print(
        "\nDEPTH"
    )


    print(
        "  RIGHT Min:",
        format_number(
            summary[
                "right_ratio_min"
            ]
        )
    )


    print(
        "  LEFT Min :",
        format_number(
            summary[
                "left_ratio_min"
            ]
        )
    )


    print(
        "  Bilateral Max MIN:",
        format_number(
            summary[
                "bilateral_max_min"
            ]
        )
    )


    print(
        "  Gap Median:",
        format_number(
            summary[
                "gap_median"
            ]
        )
    )


    # ======================================================
    # Deepest Moment
    # ======================================================

    print(
        "\nDEEPEST BILATERAL MOMENT"
    )


    print(
        "  Time:",
        format_number(
            summary[
                "deepest_time"
            ],
            3
        ),
        "sec"
    )


    print(
        "  RIGHT:",
        format_number(
            summary[
                "deepest_right_ratio"
            ]
        )
    )


    print(
        "  LEFT :",
        format_number(
            summary[
                "deepest_left_ratio"
            ]
        )
    )


    print(
        "  Bilateral Max:",
        format_number(
            summary[
                "deepest_bilateral_max"
            ]
        )
    )


    print(
        "  Gap:",
        format_number(
            summary[
                "deepest_gap"
            ]
        )
    )


    # ======================================================
    # Close
    # ======================================================

    print(
        "\nCLOSE TIMING"
    )


    print(
        "  RIGHT Close:",
        format_number(
            summary[
                "right_close_time"
            ],
            3
        ),
        "sec"
    )


    print(
        "  LEFT Close :",
        format_number(
            summary[
                "left_close_time"
            ],
            3
        ),
        "sec"
    )


    print(
        "  Close Sync :",
        format_number(
            summary[
                "close_sync_seconds"
            ],
            3
        ),
        "sec"
    )


    # ======================================================
    # Reopen
    # ======================================================

    print(
        "\nREOPEN TIMING"
    )


    print(
        "  RIGHT Reopen:",
        format_number(
            summary[
                "right_reopen_time"
            ],
            3
        ),
        "sec"
    )


    print(
        "  LEFT Reopen :",
        format_number(
            summary[
                "left_reopen_time"
            ],
            3
        ),
        "sec"
    )


    print(
        "  Reopen Sync :",
        format_number(
            summary[
                "reopen_sync_seconds"
            ],
            3
        ),
        "sec"
    )


    # ======================================================
    # Duration
    # ======================================================

    print(
        "\nCLOSED DURATION"
    )


    print(
        "  RIGHT:",
        format_number(
            summary[
                "right_closed_duration"
            ],
            3
        ),
        "sec"
    )


    print(
        "  LEFT :",
        format_number(
            summary[
                "left_closed_duration"
            ],
            3
        ),
        "sec"
    )


    print(
        "  BOTH :",
        format_number(
            summary[
                "both_closed_duration"
            ],
            3
        ),
        "sec"
    )


    print(
        "  Duration Gap:",
        format_number(
            summary[
                "closed_duration_gap"
            ],
            3
        ),
        "sec"
    )


    # ======================================================
    # Current Blink Detector
    # ======================================================

    print(
        "\nCURRENT BLINK DETECTOR"
    )


    print(
        "  Blink Events:",
        summary[
            "blink_event_count"
        ]
    )


    print(
        "  Blink Duration:",
        format_number(
            summary[
                "blink_duration_max"
            ],
            3
        ),
        "sec"
    )


    print(
        "########################################################"
    )


# ==========================================================
# Final Summary
# ==========================================================

def print_final_summary(
    summaries
):

    print(
        "\n\n"
        "========================================================"
    )


    print(
        "POSTGUARD EVENT-CENTERED BLINK FINAL SUMMARY"
    )


    print(
        "========================================================"
    )


    for test_type in (

        "TRUE_BLINK",
        "LEFT_WINK",
        "RIGHT_WINK",

    ):

        rows = [

            row

            for row in summaries

            if row[
                "test_type"
            ]
            ==
            test_type
        ]


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


        # ==================================================
        # Each Round
        # ==================================================

        for row in rows:

            print(

                f"Round {row['round']}: "

                f"Depth="
                f"{format_number(row['bilateral_max_min'])} | "

                f"CloseSync="
                f"{format_number(row['close_sync_seconds'], 3)}s | "

                f"ReopenSync="
                f"{format_number(row['reopen_sync_seconds'], 3)}s | "

                f"RClosed="
                f"{format_number(row['right_closed_duration'], 3)}s | "

                f"LClosed="
                f"{format_number(row['left_closed_duration'], 3)}s | "

                f"BothClosed="
                f"{format_number(row['both_closed_duration'], 3)}s | "

                f"DurationGap="
                f"{format_number(row['closed_duration_gap'], 3)}s | "

                f"BlinkEvents="
                f"{row['blink_event_count']}"
            )


        if not rows:

            continue


        # ==================================================
        # Group Values
        # ==================================================

        depth_values = [

            row[
                "bilateral_max_min"
            ]

            for row in rows

            if row[
                "bilateral_max_min"
            ]
            is not None
        ]


        close_sync_values = [

            row[
                "close_sync_seconds"
            ]

            for row in rows

            if row[
                "close_sync_seconds"
            ]
            is not None
        ]


        reopen_sync_values = [

            row[
                "reopen_sync_seconds"
            ]

            for row in rows

            if row[
                "reopen_sync_seconds"
            ]
            is not None
        ]


        duration_gap_values = [

            row[
                "closed_duration_gap"
            ]

            for row in rows
        ]


        detector_events = sum(

            row[
                "blink_event_count"
            ]

            for row in rows
        )


        # ==================================================
        # Group Summary
        # ==================================================

        print()


        print(
            "Group Depth Median:",
            format_number(
                safe_median(
                    depth_values
                )
            )
        )


        print(
            "Group Close Sync Median:",
            format_number(
                safe_median(
                    close_sync_values
                ),
                3
            ),
            "sec"
        )


        print(
            "Group Reopen Sync Median:",
            format_number(
                safe_median(
                    reopen_sync_values
                ),
                3
            ),
            "sec"
        )


        print(
            "Closed Duration Gap Median:",
            format_number(
                safe_median(
                    duration_gap_values
                ),
                3
            ),
            "sec"
        )


        print(
            "Blink Events Total:",
            detector_events
        )


    print(
        "\n"
        "========================================================"
    )


    print(
        "DIAGNOSTIC COMPLETE"
    )


    print(
        "Do NOT modify BlinkDetector thresholds yet."
    )


    print(
        "========================================================"
    )


# ==========================================================
# Save Raw CSV
# ==========================================================

def save_raw_csv(
    rows,
    output_path
):

    fieldnames = [

        "test_type",
        "round",

        "frame_index",

        "capture_elapsed",
        "event_elapsed",

        "measurement_valid",

        "right_openness",
        "left_openness",

        "right_open_reference",
        "left_open_reference",

        "right_ratio",
        "left_ratio",

        "bilateral_max",
        "bilateral_min",
        "ratio_gap",

        "right_state",
        "left_state",
        "combined_state",

        "blink_event",
        "blink_duration",
        "blink_reason",
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
# Main
# ==========================================================

def main():

    # ======================================================
    # Check Model
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
    # Face Detector
    # ======================================================

    face_detector = (
        FaceDetector(
            FACE_MODEL_PATH
        )
    )


    # ======================================================
    # Eye State Detector
    # ======================================================

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


    # ======================================================
    # Existing Blink Detector
    # ======================================================

    blink_detector = (
        BlinkDetector(

            min_blink_seconds=(
                MIN_BLINK_SECONDS
            ),

            max_blink_seconds=(
                MAX_BLINK_SECONDS
            ),

            max_close_sync_seconds=(
                MAX_CLOSE_SYNC_SECONDS
            ),
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
    # Result Folder
    # ======================================================

    results_dir = (

        BASE_DIR

        / "mediapipe_detection"

        / "tests"

        / "results"
    )


    results_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    output_timestamp = (

        datetime.now()

        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )


    raw_path = (

        results_dir

        /

        (
            "blink_event_centered_raw_"

            +

            output_timestamp

            +

            ".csv"
        )
    )


    summary_path = (

        results_dir

        /

        (
            "blink_event_centered_summary_"

            +

            output_timestamp

            +

            ".csv"
        )
    )


    # ======================================================
    # Runtime
    # ======================================================

    program_started_at = (
        time.perf_counter()
    )


    calibration_started = False

    calibration_printed = False


    right_open_reference = None

    left_open_reference = None


    test_index = 0


    preparing = False

    collecting = False


    prepare_started_at = None

    capture_started_at = None


    # ======================================================
    # Event Runtime
    # ======================================================

    event_active = False

    event_started_at = None

    open_stable_started_at = None


    previous_right_state = None

    previous_left_state = None


    frame_index = 0


    current_event_rows = []

    all_raw_rows = []

    summaries = []


    diagnostic_complete = False


    status_message = (
        "Preparing calibration..."
    )


    # ======================================================
    # Terminal Instructions
    # ======================================================

    print(
        "\n"
        "========================================================\n"
        "POSTGUARD EVENT-CENTERED BLINK DIAGNOSTIC\n"
        "========================================================\n"
        "\n"
        "TRUE_BLINK x5\n"
        "LEFT_WINK  x3\n"
        "RIGHT_WINK x3\n"
        "\n"
        "1 physical action = 1 captured event\n"
        "\n"
        "SPACE = start round\n"
        "R     = restart entire diagnostic\n"
        "Q/ESC = quit\n"
        "\n"
        "IMPORTANT:\n"
        "Keep BOTH eyes naturally open during PREPARE.\n"
        "Perform action only when WAITING FOR ACTION appears.\n"
        "========================================================\n"
    )


    # ======================================================
    # Camera Loop
    # ======================================================

    while True:

        # ==================================================
        # Read Frame
        # ==================================================

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
        #
        # ใช้ production measurement layer เดิม
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
        # Automatic Calibration
        # ==================================================

        if (
            not calibration_started

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


            blink_detector.reset()


            calibration_started = True


            status_message = (
                "CALIBRATING - KEEP BOTH EYES OPEN"
            )


            print(
                "\nCalibration started."
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


        # ==================================================
        # Existing Blink Detector
        # ==================================================

        blink_result = blink_detector.update(
            eye_state_result,
            eye_measurement=eye_measurement,
            timestamp=now,
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


            blink_detector.reset()


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


            print(
                "\nPress SPACE when ready."
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


            # ------------------------------------------------
            # Feed OPEN states into temporal detector
            # ------------------------------------------------

            previous_right_state = (
                right_state
            )


            previous_left_state = (
                left_state
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


                event_active = False

                event_started_at = None

                open_stable_started_at = None


                current_event_rows = []

                frame_index = 0


                current_test = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                status_message = (
                    "WAITING FOR ACTION"
                )


                print(
                    "\n"
                    "=============================================="
                )


                print(
                    "WAITING FOR ACTION"
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
        # Event Collection
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


            # =================================================
            # Normalized Eye Ratios
            # =================================================

            (
                right_ratio,
                left_ratio,

            ) = calculate_normalized_ratios(

                eye_measurement,

                right_open_reference,

                left_open_reference
            )


            # =================================================
            # Detect OPEN -> CLOSED Transition
            #
            # Event เริ่มเมื่ออย่างน้อยหนึ่งตา
            # เปลี่ยน OPEN -> CLOSED
            # =================================================

            right_close_transition = (

                previous_right_state
                ==
                EYE_OPEN

                and

                right_state
                ==
                EYE_CLOSED
            )


            left_close_transition = (

                previous_left_state
                ==
                EYE_OPEN

                and

                left_state
                ==
                EYE_CLOSED
            )


            if (
                not event_active

                and

                (
                    right_close_transition

                    or

                    left_close_transition
                )
            ):

                event_active = True


                event_started_at = (
                    now
                )


                open_stable_started_at = (
                    None
                )


                current_event_rows = []

                frame_index = 0


                status_message = (
                    "EVENT ACTIVE"
                )


                print(
                    "\n>>> EVENT STARTED <<<"
                )


            # =================================================
            # EVENT ACTIVE
            # =================================================

            if event_active:

                event_elapsed = (

                    now

                    -

                    event_started_at
                )


                frame_index += 1


                # =============================================
                # Bilateral Ratios
                # =============================================

                if (
                    right_ratio is not None

                    and

                    left_ratio is not None
                ):

                    bilateral_max = max(

                        right_ratio,

                        left_ratio
                    )


                    bilateral_min = min(

                        right_ratio,

                        left_ratio
                    )


                    ratio_gap = abs(

                        right_ratio

                        -

                        left_ratio
                    )


                else:

                    bilateral_max = None

                    bilateral_min = None

                    ratio_gap = None


                # =============================================
                # Raw Openness
                # =============================================

                if eye_measurement is not None:

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


                else:

                    right_openness = None

                    left_openness = None


                # =============================================
                # Blink Result
                # =============================================

                blink_duration = (
                    blink_result.get(
                        "last_blink_duration"
                    )
                )


                blink_reason = (
                    blink_result.get(
                        "reason"
                    )
                )


                # =============================================
                # Save Current Frame
                # =============================================

                row = {

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

                    "capture_elapsed": (
                        float(
                            capture_elapsed
                        )
                    ),

                    "event_elapsed": (
                        float(
                            event_elapsed
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

                    "bilateral_max": (
                        bilateral_max
                    ),

                    "bilateral_min": (
                        bilateral_min
                    ),

                    "ratio_gap": (
                        ratio_gap
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

                    "blink_event": (
                        bool(
                            blink_result[
                                "blink_event"
                            ]
                        )
                    ),

                    "blink_duration": (
                        blink_duration
                    ),

                    "blink_reason": (
                        blink_reason
                    ),
                }


                current_event_rows.append(
                    row
                )


                # =============================================
                # Blink Event Log
                # =============================================

                if blink_result[
                    "blink_event"
                ]:

                    print(
                        "BLINK DETECTOR EVENT",
                        (
                            "duration="
                            +
                            format_number(
                                blink_duration,
                                3
                            )
                            +
                            "s"
                        )
                    )


                # =============================================
                # Return To OPEN
                # =============================================

                both_open = (

                    right_state
                    ==
                    EYE_OPEN

                    and

                    left_state
                    ==
                    EYE_OPEN
                )


                if both_open:

                    if (
                        open_stable_started_at
                        is None
                    ):

                        open_stable_started_at = (
                            now
                        )


                    stable_open_duration = (

                        now

                        -

                        open_stable_started_at
                    )


                    # =========================================
                    # EVENT COMPLETE
                    # =========================================

                    if (
                        stable_open_duration
                        >=
                        RETURN_OPEN_STABLE_SECONDS
                    ):

                        event_active = False

                        collecting = False


                        summary = (
                            analyze_event(
                                current_event_rows
                            )
                        )


                        # =====================================
                        # Data Quality
                        # =====================================

                        if (
                            summary[
                                "event_frames"
                            ]
                            <
                            MIN_EVENT_FRAMES
                        ):

                            print(
                                "\nEVENT TOO SHORT"
                            )


                            print(
                                "Retry SAME round."
                            )


                            status_message = (
                                "RETRY SAME ROUND - Press SPACE"
                            )


                        else:

                            # =================================
                            # Accept Event
                            # =================================

                            all_raw_rows.extend(
                                current_event_rows
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


                            print_event_summary(

                                current_test[
                                    "test_type"
                                ],

                                current_test[
                                    "round"
                                ],

                                summary
                            )


                            # =================================
                            # Next Test
                            # =================================

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
                                    all_raw_rows,
                                    raw_path
                                )


                                save_summary_csv(
                                    summaries,
                                    summary_path
                                )


                                print_final_summary(
                                    summaries
                                )


                                print(
                                    "\nRAW CSV:"
                                )


                                print(
                                    raw_path
                                )


                                print(
                                    "\nSUMMARY CSV:"
                                )


                                print(
                                    summary_path
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
                                    "Press SPACE when ready."
                                )


                else:

                    # -----------------------------------------
                    # ยังไม่ OPEN ทั้งสองตา
                    # -----------------------------------------

                    open_stable_started_at = (
                        None
                    )


                # =============================================
                # Event Timeout
                # =============================================

                if (
                    event_active

                    and

                    event_elapsed
                    >=
                    MAX_EVENT_SECONDS
                ):

                    event_active = False

                    collecting = False


                    print(
                        "\nEVENT TIMEOUT"
                    )


                    print(
                        "Eyes did not return to stable OPEN."
                    )


                    print(
                        "Retry SAME round."
                    )


                    status_message = (
                        "RETRY SAME ROUND - Press SPACE"
                    )


            # =================================================
            # Waiting For Action Timeout
            # =================================================

            else:

                if (
                    capture_elapsed
                    >=
                    WAIT_ACTION_TIMEOUT
                ):

                    collecting = False


                    print(
                        "\nNO ACTION DETECTED"
                    )


                    print(
                        "No OPEN -> CLOSED transition detected."
                    )


                    print(
                        "Retry SAME round."
                    )


                    status_message = (
                        "RETRY SAME ROUND - Press SPACE"
                    )


            # =================================================
            # Update Previous States
            # =================================================

            previous_right_state = (
                right_state
            )


            previous_left_state = (
                left_state
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
        # Current Ratios
        # ==================================================

        (
            screen_right_ratio,
            screen_left_ratio,

        ) = calculate_normalized_ratios(

            eye_measurement,

            right_open_reference,

            left_open_reference
        )


        if (
            screen_right_ratio is not None

            and

            screen_left_ratio is not None
        ):

            cv2.putText(

                display_frame,

                (
                    "R Ratio: "
                    f"{screen_right_ratio:.3f}"
                ),

                (20, 35),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (0, 255, 255),

                2
            )


            cv2.putText(

                display_frame,

                (
                    "L Ratio: "
                    f"{screen_left_ratio:.3f}"
                ),

                (20, 70),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.55,

                (0, 255, 255),

                2
            )


            cv2.putText(

                display_frame,

                (
                    "Bilateral Max: "
                    f"{max(screen_right_ratio, screen_left_ratio):.3f}"
                ),

                (20, 105),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.50,

                (0, 255, 255),

                1
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
                    right_state
                )
            ),

            (20, 150),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.48,

            (255, 255, 255),

            1
        )


        cv2.putText(

            display_frame,

            (
                "L State: "
                +
                str(
                    left_state
                )
            ),

            (20, 180),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.48,

            (255, 255, 255),

            1
        )


        cv2.putText(

            display_frame,

            (
                "Combined: "
                +
                str(
                    combined_state
                )
            ),

            (20, 210),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.48,

            (255, 255, 255),

            1
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


            instruction = (
                current_test[
                    "instruction"
                ]
            )


        else:

            test_text = (
                "COMPLETE"
            )


            instruction = (
                "DIAGNOSTIC COMPLETE"
            )


        cv2.putText(

            display_frame,

            (
                "TEST: "
                +
                test_text
            ),

            (20, 260),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.60,

            (0, 255, 255),

            2
        )


        cv2.putText(

            display_frame,

            instruction,

            (20, 295),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.42,

            (255, 255, 255),

            1
        )


        # ==================================================
        # Runtime Text
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

                "PREPARE - KEEP BOTH EYES OPEN "

                f"{remaining:.1f}s"
            )


        elif collecting:

            if event_active:

                runtime_text = (
                    "EVENT ACTIVE"
                )


            else:

                runtime_text = (
                    "WAITING FOR ACTION"
                )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(

            display_frame,

            runtime_text,

            (20, 345),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.52,

            (0, 255, 255),

            1
        )


        cv2.putText(

            display_frame,

            "SPACE=Start  R=Restart All  Q=Quit",

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

            "PostGuard - Event Centered Blink Diagnostic",

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

            27,

        ):

            break


        # ==================================================
        # SPACE = Start Current Round
        #
        # Reset Blink Detector ก่อน PREPARE
        #
        # จากนั้น PREPARE จะ feed OPEN state ให้ detector
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

            not preparing

            and

            not collecting

            and

            not diagnostic_complete
        ):

            blink_detector.reset(
                preserve_count=True
            )


            preparing = True


            prepare_started_at = (
                now
            )


            current_event_rows = []


            event_active = False

            event_started_at = None

            open_stable_started_at = None


            previous_right_state = (
                right_state
            )


            previous_left_state = (
                left_state
            )


            current_test = (
                TEST_SEQUENCE[
                    test_index
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
                "Wait until WAITING FOR ACTION appears."
            )


            print(
                "Then:"
            )


            print(
                current_test[
                    "instruction"
                ]
            )


        # ==================================================
        # R = Restart Entire Diagnostic
        # ==================================================

        if key in (

            ord("r"),

            ord("R"),

        ):

            eye_state_detector.reset()


            blink_detector.reset()


            program_started_at = (
                time.perf_counter()
            )


            calibration_started = False

            calibration_printed = False


            right_open_reference = None

            left_open_reference = None


            test_index = 0


            preparing = False

            collecting = False


            prepare_started_at = None

            capture_started_at = None


            event_active = False

            event_started_at = None

            open_stable_started_at = None


            previous_right_state = None

            previous_left_state = None


            frame_index = 0


            current_event_rows = []

            all_raw_rows = []

            summaries = []


            diagnostic_complete = False


            status_message = (
                "RESET - Preparing calibration..."
            )


            print(
                "\nENTIRE DIAGNOSTIC RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()


    face_detector.close()


    cv2.destroyAllWindows()


# ==========================================================
# Entry
# ==========================================================

if __name__ == "__main__":

    main()