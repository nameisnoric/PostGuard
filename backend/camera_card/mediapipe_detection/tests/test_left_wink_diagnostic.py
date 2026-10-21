from pathlib import Path

import sys
import time
import csv
import math

from datetime import datetime
from statistics import median, mean, pstdev


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


from mediapipe_detection.face.face_draw import (
    draw_face_points
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


# ==========================================================
# Model Path
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Test Configuration
# ==========================================================

CALIBRATION_SECONDS = 3.0

MIN_CALIBRATION_SAMPLES = 30


# ใช้ค่าเดียวกับ Eye State ปัจจุบัน
CLOSE_FACTOR = 0.55

REOPEN_FACTOR = 0.70


# หลัง SPACE
# ให้เวลาผู้ใช้ขยิบตาซ้ายก่อนเริ่มเก็บจริง
PREPARE_SECONDS = 1.5


# เก็บ LEFT_WINK จริง
CAPTURE_SECONDS = 3.0


MIN_VALID_SAMPLES = 30


# ==========================================================
# Numeric Helpers
# ==========================================================

def is_finite_number(
    value
):
    """
    ตรวจว่าค่าเป็นตัวเลขที่ใช้งานได้
    """

    if value is None:
        return False


    try:

        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError
    ):

        return False


# ==========================================================
# Statistical Summary
# ==========================================================

def summarize(
    values
):
    """
    สรุป distribution ของค่าที่เก็บได้
    """

    clean_values = [
        float(value)
        for value in values
        if is_finite_number(
            value
        )
    ]


    if not clean_values:

        return None


    if len(
        clean_values
    ) > 1:

        std_value = pstdev(
            clean_values
        )

    else:

        std_value = 0.0


    return {

        "count": len(
            clean_values
        ),

        "median": float(
            median(
                clean_values
            )
        ),

        "mean": float(
            mean(
                clean_values
            )
        ),

        "std": float(
            std_value
        ),

        "min": float(
            min(
                clean_values
            )
        ),

        "max": float(
            max(
                clean_values
            )
        ),
    }


# ==========================================================
# Ratio Helper
# ==========================================================

def ratio(
    count,
    total
):

    if total <= 0:
        return 0.0


    return (
        count
        /
        total
    )


# ==========================================================
# Eye Width Helper
# ==========================================================

def get_eye_width(
    measurement,
    side
):
    """
    ดึง horizontal_px จาก eye_measurement.py

    Expected:

    measurement["right_eye"]["horizontal_px"]
    measurement["left_eye"]["horizontal_px"]
    """

    if measurement is None:
        return None


    eye_data = measurement.get(
        f"{side}_eye"
    )


    if not isinstance(
        eye_data,
        dict
    ):

        return None


    value = eye_data.get(
        "horizontal_px"
    )


    if not is_finite_number(
        value
    ):

        return None


    return float(
        value
    )


# ==========================================================
# Print Statistics
# ==========================================================

def print_statistics(
    name,
    summary
):

    print(
        f"\n{name}"
    )


    if summary is None:

        print(
            "  No valid samples"
        )

        return


    print(
        "  Samples:",
        summary[
            "count"
        ]
    )


    print(
        "  Median :",
        f"{summary['median']:.5f}"
    )


    print(
        "  Mean   :",
        f"{summary['mean']:.5f}"
    )


    print(
        "  Std    :",
        f"{summary['std']:.5f}"
    )


    print(
        "  Min    :",
        f"{summary['min']:.5f}"
    )


    print(
        "  Max    :",
        f"{summary['max']:.5f}"
    )


# ==========================================================
# Analyse Diagnostic
# ==========================================================

def analyse_diagnostic(
    frames,
    calibration
):

    valid_frames = [
        frame
        for frame in frames
        if frame[
            "measurement_valid"
        ]
    ]


    total = len(
        valid_frames
    )


    if total == 0:

        return None


    # ======================================================
    # References / Thresholds
    # ======================================================

    right_reference = (
        calibration[
            "right_open_reference"
        ]
    )


    right_close_threshold = (
        calibration[
            "right_close_threshold"
        ]
    )


    right_reopen_threshold = (
        calibration[
            "right_reopen_threshold"
        ]
    )


    left_reference = (
        calibration[
            "left_open_reference"
        ]
    )


    left_close_threshold = (
        calibration[
            "left_close_threshold"
        ]
    )


    left_reopen_threshold = (
        calibration[
            "left_reopen_threshold"
        ]
    )


    # ======================================================
    # Values
    # ======================================================

    right_values = [
        frame[
            "right_openness"
        ]
        for frame in valid_frames
    ]


    left_values = [
        frame[
            "left_openness"
        ]
        for frame in valid_frames
    ]


    right_width_values = [
        frame[
            "right_eye_width_px"
        ]
        for frame in valid_frames
        if is_finite_number(
            frame[
                "right_eye_width_px"
            ]
        )
    ]


    left_width_values = [
        frame[
            "left_eye_width_px"
        ]
        for frame in valid_frames
        if is_finite_number(
            frame[
                "left_eye_width_px"
            ]
        )
    ]


    # ======================================================
    # RIGHT State Counts
    # ======================================================

    right_open_count = sum(
        1
        for frame in valid_frames
        if frame[
            "right_state"
        ]
        ==
        EYE_OPEN
    )


    right_closed_count = sum(
        1
        for frame in valid_frames
        if frame[
            "right_state"
        ]
        ==
        EYE_CLOSED
    )


    right_unknown_count = sum(
        1
        for frame in valid_frames
        if frame[
            "right_state"
        ]
        ==
        EYE_UNKNOWN
    )


    # ======================================================
    # LEFT State Counts
    # ======================================================

    left_open_count = sum(
        1
        for frame in valid_frames
        if frame[
            "left_state"
        ]
        ==
        EYE_OPEN
    )


    left_closed_count = sum(
        1
        for frame in valid_frames
        if frame[
            "left_state"
        ]
        ==
        EYE_CLOSED
    )


    left_unknown_count = sum(
        1
        for frame in valid_frames
        if frame[
            "left_state"
        ]
        ==
        EYE_UNKNOWN
    )


    # ======================================================
    # Combined Counts
    # ======================================================

    combined_open_count = sum(
        1
        for frame in valid_frames
        if frame[
            "combined_state"
        ]
        ==
        EYE_OPEN
    )


    combined_closed_count = sum(
        1
        for frame in valid_frames
        if frame[
            "combined_state"
        ]
        ==
        EYE_CLOSED
    )


    combined_unknown_count = sum(
        1
        for frame in valid_frames
        if frame[
            "combined_state"
        ]
        ==
        EYE_UNKNOWN
    )


    # ======================================================
    # RIGHT Threshold Zones
    #
    # สำคัญมากสำหรับหา Root Cause
    #
    # Zone A:
    # openness <= close threshold
    #
    # Zone B:
    # close < openness < reopen
    #
    # Zone C:
    # openness >= reopen
    # ======================================================

    right_below_close = sum(
        1
        for frame in valid_frames
        if frame[
            "right_openness"
        ]
        <=
        right_close_threshold
    )


    right_hysteresis_zone = sum(
        1
        for frame in valid_frames
        if (
            frame[
                "right_openness"
            ]
            >
            right_close_threshold

            and

            frame[
                "right_openness"
            ]
            <
            right_reopen_threshold
        )
    )


    right_above_reopen = sum(
        1
        for frame in valid_frames
        if frame[
            "right_openness"
        ]
        >=
        right_reopen_threshold
    )


    # ======================================================
    # State Machine Consistency Check
    #
    # ถ้า RIGHT = CLOSED
    # แต่ openness >= reopen threshold
    #
    # หลัง update แล้ว
    # มันควรกลับ OPEN
    #
    # ถ้ายัง CLOSED ถือว่าน่าสงสัยว่า logic ผิด
    # ======================================================

    right_logic_inconsistency = [
        frame
        for frame in valid_frames
        if (
            frame[
                "right_state"
            ]
            ==
            EYE_CLOSED

            and

            frame[
                "right_openness"
            ]
            >=
            right_reopen_threshold
        )
    ]


    # ======================================================
    # Transitions
    # ======================================================

    right_transitions = []

    left_transitions = []

    combined_transitions = []


    previous_right = None

    previous_left = None

    previous_combined = None


    for frame in valid_frames:

        current_right = (
            frame[
                "right_state"
            ]
        )


        current_left = (
            frame[
                "left_state"
            ]
        )


        current_combined = (
            frame[
                "combined_state"
            ]
        )


        if (
            previous_right is not None
            and
            current_right
            !=
            previous_right
        ):

            right_transitions.append(
                {
                    "frame": frame[
                        "frame_index"
                    ],

                    "time": frame[
                        "elapsed"
                    ],

                    "from": previous_right,

                    "to": current_right,

                    "openness": frame[
                        "right_openness"
                    ],
                }
            )


        if (
            previous_left is not None
            and
            current_left
            !=
            previous_left
        ):

            left_transitions.append(
                {
                    "frame": frame[
                        "frame_index"
                    ],

                    "time": frame[
                        "elapsed"
                    ],

                    "from": previous_left,

                    "to": current_left,

                    "openness": frame[
                        "left_openness"
                    ],
                }
            )


        if (
            previous_combined is not None
            and
            current_combined
            !=
            previous_combined
        ):

            combined_transitions.append(
                {
                    "frame": frame[
                        "frame_index"
                    ],

                    "time": frame[
                        "elapsed"
                    ],

                    "from": previous_combined,

                    "to": current_combined,
                }
            )


        previous_right = (
            current_right
        )


        previous_left = (
            current_left
        )


        previous_combined = (
            current_combined
        )


    # ======================================================
    # Determine Likely Cause
    #
    # นี่เป็น Diagnostic
    # ไม่ใช่ Risk Classification
    # ======================================================

    below_close_ratio = ratio(
        right_below_close,
        total
    )


    hysteresis_ratio = ratio(
        right_hysteresis_zone,
        total
    )


    closed_ratio = ratio(
        right_closed_count,
        total
    )


    inconsistency_ratio = ratio(
        len(
            right_logic_inconsistency
        ),
        total
    )


    if (
        len(
            right_logic_inconsistency
        )
        >
        0
    ):

        likely_cause = (
            "STATE_MACHINE_SUSPECT"
        )


        explanation = (
            "RIGHT eye remained CLOSED even though "
            "openness was already >= reopen threshold."
        )


    elif (
        below_close_ratio
        >=
        0.20
    ):

        likely_cause = (
            "RIGHT_OPENNESS_ACTUALLY_DROPS"
        )


        explanation = (
            "RIGHT eye openness frequently falls below "
            "the close threshold during LEFT_WINK. "
            "This points to measurement / landmark / "
            "physical co-contraction rather than a "
            "basic hysteresis implementation bug."
        )


    elif (
        closed_ratio
        >
        below_close_ratio

        and

        hysteresis_ratio
        >
        0.10
    ):

        likely_cause = (
            "TEMPORARY_DIP_WITH_HYSTERESIS_HOLD"
        )


        explanation = (
            "RIGHT openness dips below close threshold "
            "briefly and then remains inside the "
            "hysteresis band, so CLOSED is held until "
            "openness reaches reopen threshold."
        )


    else:

        likely_cause = (
            "NO_CLEAR_FAILURE_PATTERN"
        )


        explanation = (
            "This capture does not show a strong "
            "single failure pattern. More targeted "
            "measurement inspection may be needed."
        )


    # ======================================================
    # Return
    # ======================================================

    return {

        "total": total,

        "right_reference": (
            right_reference
        ),

        "right_close_threshold": (
            right_close_threshold
        ),

        "right_reopen_threshold": (
            right_reopen_threshold
        ),

        "left_reference": (
            left_reference
        ),

        "left_close_threshold": (
            left_close_threshold
        ),

        "left_reopen_threshold": (
            left_reopen_threshold
        ),

        "right_summary": (
            summarize(
                right_values
            )
        ),

        "left_summary": (
            summarize(
                left_values
            )
        ),

        "right_width_summary": (
            summarize(
                right_width_values
            )
        ),

        "left_width_summary": (
            summarize(
                left_width_values
            )
        ),

        "right_open_count": (
            right_open_count
        ),

        "right_closed_count": (
            right_closed_count
        ),

        "right_unknown_count": (
            right_unknown_count
        ),

        "left_open_count": (
            left_open_count
        ),

        "left_closed_count": (
            left_closed_count
        ),

        "left_unknown_count": (
            left_unknown_count
        ),

        "combined_open_count": (
            combined_open_count
        ),

        "combined_closed_count": (
            combined_closed_count
        ),

        "combined_unknown_count": (
            combined_unknown_count
        ),

        "right_below_close": (
            right_below_close
        ),

        "right_hysteresis_zone": (
            right_hysteresis_zone
        ),

        "right_above_reopen": (
            right_above_reopen
        ),

        "right_logic_inconsistency": (
            right_logic_inconsistency
        ),

        "right_transitions": (
            right_transitions
        ),

        "left_transitions": (
            left_transitions
        ),

        "combined_transitions": (
            combined_transitions
        ),

        "likely_cause": (
            likely_cause
        ),

        "explanation": (
            explanation
        ),
    }


# ==========================================================
# Print Diagnostic
# ==========================================================

def print_diagnostic(
    report
):

    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD LEFT WINK DIAGNOSTIC"
    )


    print(
        "################################################"
    )


    if report is None:

        print(
            "No valid samples."
        )

        return


    total = (
        report[
            "total"
        ]
    )


    # ======================================================
    # Calibration
    # ======================================================

    print(
        "\nRIGHT EYE CALIBRATION"
    )


    print(
        "Open Reference   :",
        f"{report['right_reference']:.5f}"
    )


    print(
        "Close Threshold  :",
        f"{report['right_close_threshold']:.5f}"
    )


    print(
        "Reopen Threshold :",
        f"{report['right_reopen_threshold']:.5f}"
    )


    print(
        "\nLEFT EYE CALIBRATION"
    )


    print(
        "Open Reference   :",
        f"{report['left_reference']:.5f}"
    )


    print(
        "Close Threshold  :",
        f"{report['left_close_threshold']:.5f}"
    )


    print(
        "Reopen Threshold :",
        f"{report['left_reopen_threshold']:.5f}"
    )


    # ======================================================
    # Openness Distribution
    # ======================================================

    print_statistics(
        "RIGHT OPENNESS DURING LEFT_WINK",
        report[
            "right_summary"
        ]
    )


    print_statistics(
        "LEFT OPENNESS DURING LEFT_WINK",
        report[
            "left_summary"
        ]
    )


    # ======================================================
    # Eye Scale
    #
    # Diagnostic only
    # ไม่ได้ใช้บังคับระยะ
    # ======================================================

    print_statistics(
        "RIGHT EYE WIDTH (px)",
        report[
            "right_width_summary"
        ]
    )


    print_statistics(
        "LEFT EYE WIDTH (px)",
        report[
            "left_width_summary"
        ]
    )


    # ======================================================
    # State Counts
    # ======================================================

    print(
        "\n------------------------------------------------"
    )


    print(
        "RIGHT STATE"
    )


    print(
        "OPEN:",
        report[
            "right_open_count"
        ],
        f"({ratio(report['right_open_count'], total):.1%})"
    )


    print(
        "CLOSED:",
        report[
            "right_closed_count"
        ],
        f"({ratio(report['right_closed_count'], total):.1%})"
    )


    print(
        "UNKNOWN:",
        report[
            "right_unknown_count"
        ],
        f"({ratio(report['right_unknown_count'], total):.1%})"
    )


    print(
        "\nLEFT STATE"
    )


    print(
        "OPEN:",
        report[
            "left_open_count"
        ],
        f"({ratio(report['left_open_count'], total):.1%})"
    )


    print(
        "CLOSED:",
        report[
            "left_closed_count"
        ],
        f"({ratio(report['left_closed_count'], total):.1%})"
    )


    print(
        "UNKNOWN:",
        report[
            "left_unknown_count"
        ],
        f"({ratio(report['left_unknown_count'], total):.1%})"
    )


    print(
        "\nCOMBINED STATE"
    )


    print(
        "OPEN:",
        report[
            "combined_open_count"
        ],
        f"({ratio(report['combined_open_count'], total):.1%})"
    )


    print(
        "CLOSED:",
        report[
            "combined_closed_count"
        ],
        f"({ratio(report['combined_closed_count'], total):.1%})"
    )


    print(
        "UNKNOWN:",
        report[
            "combined_unknown_count"
        ],
        f"({ratio(report['combined_unknown_count'], total):.1%})"
    )


    # ======================================================
    # Threshold Zones
    # ======================================================

    print(
        "\n------------------------------------------------"
    )


    print(
        "RIGHT OPENNESS THRESHOLD ZONES"
    )


    print(
        "<= Close Threshold:",
        report[
            "right_below_close"
        ],
        f"({ratio(report['right_below_close'], total):.1%})"
    )


    print(
        "Inside Hysteresis Band:",
        report[
            "right_hysteresis_zone"
        ],
        f"({ratio(report['right_hysteresis_zone'], total):.1%})"
    )


    print(
        ">= Reopen Threshold:",
        report[
            "right_above_reopen"
        ],
        f"({ratio(report['right_above_reopen'], total):.1%})"
    )


    # ======================================================
    # Logic Consistency
    # ======================================================

    inconsistency_count = len(
        report[
            "right_logic_inconsistency"
        ]
    )


    print(
        "\nRIGHT STATE-MACHINE INCONSISTENCY:"
    )


    print(
        inconsistency_count,
        "frames"
    )


    if inconsistency_count == 0:

        print(
            "PASS - No CLOSED frame was found while "
            "openness >= reopen threshold."
        )

    else:

        print(
            "SUSPECT - Eye State implementation needs review."
        )


    # ======================================================
    # RIGHT Transitions
    # ======================================================

    print(
        "\n------------------------------------------------"
    )


    print(
        "RIGHT EYE TRANSITIONS"
    )


    if not report[
        "right_transitions"
    ]:

        print(
            "No transition."
        )


    else:

        for transition in report[
            "right_transitions"
        ]:

            print(
                (
                    f"Frame {transition['frame']:03d} "
                    f"t={transition['time']:.3f}s "
                    f"{transition['from']} "
                    f"-> {transition['to']} "
                    f"openness={transition['openness']:.5f}"
                )
            )


    # ======================================================
    # LEFT Transitions
    # ======================================================

    print(
        "\nLEFT EYE TRANSITIONS"
    )


    if not report[
        "left_transitions"
    ]:

        print(
            "No transition."
        )


    else:

        for transition in report[
            "left_transitions"
        ]:

            print(
                (
                    f"Frame {transition['frame']:03d} "
                    f"t={transition['time']:.3f}s "
                    f"{transition['from']} "
                    f"-> {transition['to']} "
                    f"openness={transition['openness']:.5f}"
                )
            )


    # ======================================================
    # Conclusion
    # ======================================================

    print(
        "\n================================================"
    )


    print(
        "LIKELY CAUSE:"
    )


    print(
        report[
            "likely_cause"
        ]
    )


    print(
        "\n",
        report[
            "explanation"
        ],
        sep=""
    )


    print(
        "================================================"
    )


# ==========================================================
# Save Raw Frames CSV
# ==========================================================

def save_csv(
    frames,
    report
):

    output_dir = (
        BASE_DIR
        / "mediapipe_detection"
        / "tests"
        / "results"
    )


    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    timestamp = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )


    output_path = (
        output_dir
        /
        (
            "left_wink_diagnostic_"
            +
            timestamp
            +
            ".csv"
        )
    )


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file
        )


        writer.writerow(
            [
                "frame_index",
                "elapsed",

                "measurement_valid",

                "right_openness",
                "left_openness",

                "right_eye_width_px",
                "left_eye_width_px",

                "right_state",
                "left_state",
                "combined_state",

                "right_open_reference",
                "right_close_threshold",
                "right_reopen_threshold",

                "left_open_reference",
                "left_close_threshold",
                "left_reopen_threshold",
            ]
        )


        for frame in frames:

            writer.writerow(
                [
                    frame[
                        "frame_index"
                    ],

                    frame[
                        "elapsed"
                    ],

                    frame[
                        "measurement_valid"
                    ],

                    frame[
                        "right_openness"
                    ],

                    frame[
                        "left_openness"
                    ],

                    frame[
                        "right_eye_width_px"
                    ],

                    frame[
                        "left_eye_width_px"
                    ],

                    frame[
                        "right_state"
                    ],

                    frame[
                        "left_state"
                    ],

                    frame[
                        "combined_state"
                    ],

                    frame[
                        "right_open_reference"
                    ],

                    frame[
                        "right_close_threshold"
                    ],

                    frame[
                        "right_reopen_threshold"
                    ],

                    frame[
                        "left_open_reference"
                    ],

                    frame[
                        "left_close_threshold"
                    ],

                    frame[
                        "left_reopen_threshold"
                    ],
                ]
            )


    print(
        "\nRaw diagnostic CSV saved:"
    )


    print(
        output_path
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
    # Runtime
    # ======================================================

    calibration_printed = False


    preparing = False

    collecting = False


    prepare_started_at = None

    capture_started_at = None


    frames = []


    diagnostic_complete = False


    status_message = (
        "Press C to calibrate"
    )


    # ======================================================
    # Terminal Instructions
    # ======================================================

    print(
        "\n"
        "================================================\n"
        "POSTGUARD LEFT WINK DIAGNOSTIC\n"
        "================================================\n"
        "\n"
        "PURPOSE:\n"
        "Find why RIGHT eye becomes CLOSED during LEFT_WINK.\n"
        "\n"
        "IMPORTANT:\n"
        "Sit in your NATURAL normal working position.\n"
        "Do NOT move closer to the camera for this test.\n"
        "\n"
        "STEP 1:\n"
        "Press C and keep BOTH eyes naturally OPEN\n"
        "for 3-second calibration.\n"
        "\n"
        "STEP 2:\n"
        "After calibration press SPACE.\n"
        "During PREPARE close your LEFT eye only.\n"
        "Keep your RIGHT eye naturally open.\n"
        "\n"
        "Controls:\n"
        "C     = calibrate\n"
        "SPACE = start LEFT_WINK capture\n"
        "R     = reset\n"
        "Q/ESC = quit\n"
        "================================================\n"
    )


    # ======================================================
    # Camera Loop
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


        # ==================================================
        # Eye State
        # ==================================================

        now = (
            time.perf_counter()
        )


        eye_state_result = (
            eye_state_detector.update(
                eye_measurement,
                timestamp=now
            )
        )


        # ==================================================
        # Calibration Complete
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


            status_message = (
                "Calibration READY - Press SPACE"
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
                f"{eye_state_result['right_open_reference']:.5f}"
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
                f"{eye_state_result['left_open_reference']:.5f}"
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
        # Prepare
        # ==================================================

        if preparing:

            prepare_elapsed = (
                time.perf_counter()
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
                    time.perf_counter()
                )


                frames = []


                print(
                    "\nCAPTURE STARTED"
                )


                print(
                    "Keep LEFT eye CLOSED."
                )


                print(
                    "Keep RIGHT eye naturally OPEN."
                )


        # ==================================================
        # Collect
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                -
                capture_started_at
            )


            measurement_valid = (
                eye_measurement
                is not None
            )


            if measurement_valid:

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


                right_eye_width_px = (
                    get_eye_width(
                        eye_measurement,
                        "right"
                    )
                )


                left_eye_width_px = (
                    get_eye_width(
                        eye_measurement,
                        "left"
                    )
                )


            else:

                right_openness = None

                left_openness = None


                right_eye_width_px = None

                left_eye_width_px = None


            frames.append(
                {

                    "frame_index": len(
                        frames
                    ),

                    "elapsed": float(
                        elapsed
                    ),

                    "measurement_valid": (
                        measurement_valid
                    ),

                    "right_openness": (
                        right_openness
                    ),

                    "left_openness": (
                        left_openness
                    ),

                    "right_eye_width_px": (
                        right_eye_width_px
                    ),

                    "left_eye_width_px": (
                        left_eye_width_px
                    ),

                    "right_state": (
                        eye_state_result[
                            "right_eye_state"
                        ]
                    ),

                    "left_state": (
                        eye_state_result[
                            "left_eye_state"
                        ]
                    ),

                    "combined_state": (
                        eye_state_result[
                            "eye_state"
                        ]
                    ),

                    "right_open_reference": (
                        eye_state_result[
                            "right_open_reference"
                        ]
                    ),

                    "right_close_threshold": (
                        eye_state_result[
                            "right_close_threshold"
                        ]
                    ),

                    "right_reopen_threshold": (
                        eye_state_result[
                            "right_reopen_threshold"
                        ]
                    ),

                    "left_open_reference": (
                        eye_state_result[
                            "left_open_reference"
                        ]
                    ),

                    "left_close_threshold": (
                        eye_state_result[
                            "left_close_threshold"
                        ]
                    ),

                    "left_reopen_threshold": (
                        eye_state_result[
                            "left_reopen_threshold"
                        ]
                    ),
                }
            )


            # ==============================================
            # Capture Finished
            # ==============================================

            if (
                elapsed
                >=
                CAPTURE_SECONDS
            ):

                collecting = False


                valid_count = sum(
                    1
                    for frame in frames
                    if frame[
                        "measurement_valid"
                    ]
                )


                if (
                    valid_count
                    <
                    MIN_VALID_SAMPLES
                ):

                    print(
                        "\nNot enough valid samples."
                    )


                    print(
                        "Press SPACE to retry."
                    )


                    frames = []


                    status_message = (
                        "RETRY LEFT_WINK"
                    )


                else:

                    report = (
                        analyse_diagnostic(
                            frames,
                            eye_state_result
                        )
                    )


                    print_diagnostic(
                        report
                    )


                    save_csv(
                        frames,
                        report
                    )


                    diagnostic_complete = True


                    status_message = (
                        "DIAGNOSTIC COMPLETE"
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


        display_frame = (
            draw_face_points(
                display_frame,
                face_points,
                mirrored=True
            )
        )


        # ==================================================
        # Display Calibration
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "Calibration: "
                +
                eye_state_result[
                    "calibration_status"
                ]
            ),
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2
        )


        # ==================================================
        # Display Openness
        # ==================================================

        if eye_measurement is not None:

            cv2.putText(
                display_frame,
                (
                    "RIGHT openness: "
                    f"{eye_measurement['right_eye_openness']:.4f}"
                ),
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1
            )


            cv2.putText(
                display_frame,
                (
                    "LEFT openness: "
                    f"{eye_measurement['left_eye_openness']:.4f}"
                ),
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1
            )


            right_width = (
                get_eye_width(
                    eye_measurement,
                    "right"
                )
            )


            left_width = (
                get_eye_width(
                    eye_measurement,
                    "left"
                )
            )


            if (
                right_width is not None
                and
                left_width is not None
            ):

                cv2.putText(
                    display_frame,
                    (
                        "Eye Width px "
                        f"R={right_width:.1f} "
                        f"L={left_width:.1f}"
                    ),
                    (20, 135),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.48,
                    (255, 255, 255),
                    1
                )


        # ==================================================
        # Display Thresholds
        # ==================================================

        if eye_state_result[
            "calibrated"
        ]:

            cv2.putText(
                display_frame,
                (
                    "RIGHT threshold "
                    f"C={eye_state_result['right_close_threshold']:.3f} "
                    f"R={eye_state_result['right_reopen_threshold']:.3f}"
                ),
                (20, 170),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.46,
                (255, 255, 255),
                1
            )


        # ==================================================
        # Display States
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "RIGHT STATE: "
                +
                eye_state_result[
                    "right_eye_state"
                ]
            ),
            (20, 210),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            (
                "LEFT STATE: "
                +
                eye_state_result[
                    "left_eye_state"
                ]
            ),
            (20, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            (
                "COMBINED: "
                +
                eye_state_result[
                    "eye_state"
                ]
            ),
            (20, 275),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )


        # ==================================================
        # Runtime Instruction
        # ==================================================

        if preparing:

            remaining = max(
                0.0,
                PREPARE_SECONDS
                -
                (
                    time.perf_counter()
                    -
                    prepare_started_at
                )
            )


            runtime_text = (
                "PREPARE LEFT_WINK "
                f"{remaining:.1f}s"
            )


        elif collecting:

            elapsed = min(
                CAPTURE_SECONDS,
                (
                    time.perf_counter()
                    -
                    capture_started_at
                )
            )


            runtime_text = (
                "CAPTURE LEFT_WINK "
                f"{elapsed:.1f}/"
                f"{CAPTURE_SECONDS:.1f}s"
            )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            runtime_text,
            (20, 315),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            "Sit naturally - do NOT move closer",
            (20, 345),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 255),
            1
        )


        cv2.putText(
            display_frame,
            "C=Calibrate SPACE=LEFT_WINK R=Reset Q=Quit",
            (
                20,
                frame_height - 25
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.43,
            (255, 255, 255),
            1
        )


        cv2.imshow(
            "PostGuard - LEFT WINK Diagnostic",
            display_frame
        )


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
        # Calibration
        # ==================================================

        if key in (
            ord("c"),
            ord("C")
        ):

            eye_state_detector.start_calibration(
                timestamp=time.perf_counter()
            )


            calibration_printed = False


            preparing = False

            collecting = False


            diagnostic_complete = False


            frames = []


            status_message = (
                "CALIBRATING - BOTH EYES OPEN"
            )


            print(
                "\nCalibration started."
            )


            print(
                "Keep BOTH eyes naturally OPEN."
            )


        # ==================================================
        # SPACE
        # ==================================================

        if (
            key
            ==
            ord(" ")

            and

            eye_state_result[
                "calibrated"
            ]

            and

            not preparing

            and

            not collecting
        ):

            preparing = True


            prepare_started_at = (
                time.perf_counter()
            )


            frames = []


            diagnostic_complete = False


            status_message = (
                "PREPARE LEFT_WINK"
            )


            print(
                "\nPrepare LEFT_WINK"
            )


            print(
                "Close your anatomical LEFT eye."
            )


            print(
                "Keep your RIGHT eye naturally OPEN."
            )


        # ==================================================
        # Reset
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            eye_state_detector.reset()


            calibration_printed = False


            preparing = False

            collecting = False


            prepare_started_at = None

            capture_started_at = None


            frames = []


            diagnostic_complete = False


            status_message = (
                "RESET - Press C to calibrate"
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