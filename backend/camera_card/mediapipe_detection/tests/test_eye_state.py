from pathlib import Path

import sys
import time
import csv

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
# Model
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Test Configuration
# ==========================================================

PREPARE_DURATION_SECONDS = 1.5

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# State PASS Ratio
#
# OPEN / CLOSED ต้องถูกอย่างน้อย 90%
# ==========================================================

MIN_EXPECTED_STATE_RATIO = 0.90


# ==========================================================
# Wink Criteria
#
# ขยิบตาข้างเดียว:
#
# combined CLOSED ต้องต่ำมาก
#
# และ UNKNOWN ควรเป็น state หลัก
# ==========================================================

MAX_WINK_CLOSED_RATIO = 0.10

MIN_WINK_UNKNOWN_RATIO = 0.60

MIN_WINK_TARGET_EYE_CLOSED_RATIO = 0.80

MIN_WINK_OTHER_EYE_OPEN_RATIO = 0.80


# ==========================================================
# Test Sequence
#
# 3 rounds:
#
# OPEN_1
# CLOSED
# OPEN_2
#
# แล้วทดสอบ Wink อีก 2 แบบ
# ==========================================================

TEST_SEQUENCE = []


for round_number in range(
    1,
    4
):

    TEST_SEQUENCE.extend(
        [
            {
                "round": round_number,
                "state": "OPEN_1",
                "expected": "OPEN",
            },

            {
                "round": round_number,
                "state": "CLOSED",
                "expected": "CLOSED",
            },

            {
                "round": round_number,
                "state": "OPEN_2",
                "expected": "OPEN",
            },
        ]
    )


TEST_SEQUENCE.extend(
    [
        {
            "round": 0,
            "state": "RIGHT_WINK",
            "expected": "RIGHT_WINK",
        },

        {
            "round": 0,
            "state": "LEFT_WINK",
            "expected": "LEFT_WINK",
        },
    ]
)


# ==========================================================
# Instruction
# ==========================================================

def get_instruction(
    state
):

    if state.startswith(
        "OPEN"
    ):

        return (
            "KEEP BOTH EYES NATURALLY OPEN"
        )


    if state == "CLOSED":

        return (
            "CLOSE BOTH EYES NATURALLY"
        )


    if state == "RIGHT_WINK":

        return (
            "CLOSE YOUR RIGHT EYE ONLY"
        )


    if state == "LEFT_WINK":

        return (
            "CLOSE YOUR LEFT EYE ONLY"
        )


    return state


# ==========================================================
# Empty State Counter
# ==========================================================

def make_state_counter():

    return {

        EYE_OPEN: 0,

        EYE_CLOSED: 0,

        EYE_UNKNOWN: 0,
    }


# ==========================================================
# Ratio Helper
# ==========================================================

def state_ratio(
    counter,
    state,
    total
):

    if total <= 0:

        return 0.0


    return (
        counter[
            state
        ]
        /
        total
    )


# ==========================================================
# Evaluate Capture
# ==========================================================

def evaluate_capture(
    step,
    valid_samples,
    combined_counter,
    right_counter,
    left_counter
):

    expected = (
        step[
            "expected"
        ]
    )


    # ======================================================
    # Basic State Ratios
    # ======================================================

    combined_open_ratio = (
        state_ratio(
            combined_counter,
            EYE_OPEN,
            valid_samples
        )
    )


    combined_closed_ratio = (
        state_ratio(
            combined_counter,
            EYE_CLOSED,
            valid_samples
        )
    )


    combined_unknown_ratio = (
        state_ratio(
            combined_counter,
            EYE_UNKNOWN,
            valid_samples
        )
    )


    right_open_ratio = (
        state_ratio(
            right_counter,
            EYE_OPEN,
            valid_samples
        )
    )


    right_closed_ratio = (
        state_ratio(
            right_counter,
            EYE_CLOSED,
            valid_samples
        )
    )


    left_open_ratio = (
        state_ratio(
            left_counter,
            EYE_OPEN,
            valid_samples
        )
    )


    left_closed_ratio = (
        state_ratio(
            left_counter,
            EYE_CLOSED,
            valid_samples
        )
    )


    # ======================================================
    # Expected OPEN
    # ======================================================

    if expected == "OPEN":

        passed = (
            combined_open_ratio
            >=
            MIN_EXPECTED_STATE_RATIO
        )


    # ======================================================
    # Expected CLOSED
    # ======================================================

    elif expected == "CLOSED":

        passed = (
            combined_closed_ratio
            >=
            MIN_EXPECTED_STATE_RATIO
        )


    # ======================================================
    # RIGHT WINK
    #
    # User's anatomical right eye:
    #
    # Right CLOSED
    # Left OPEN
    # Combined UNKNOWN
    # ======================================================

    elif expected == "RIGHT_WINK":

        passed = (

            right_closed_ratio
            >=
            MIN_WINK_TARGET_EYE_CLOSED_RATIO

            and

            left_open_ratio
            >=
            MIN_WINK_OTHER_EYE_OPEN_RATIO

            and

            combined_closed_ratio
            <=
            MAX_WINK_CLOSED_RATIO

            and

            combined_unknown_ratio
            >=
            MIN_WINK_UNKNOWN_RATIO
        )


    # ======================================================
    # LEFT WINK
    # ======================================================

    elif expected == "LEFT_WINK":

        passed = (

            left_closed_ratio
            >=
            MIN_WINK_TARGET_EYE_CLOSED_RATIO

            and

            right_open_ratio
            >=
            MIN_WINK_OTHER_EYE_OPEN_RATIO

            and

            combined_closed_ratio
            <=
            MAX_WINK_CLOSED_RATIO

            and

            combined_unknown_ratio
            >=
            MIN_WINK_UNKNOWN_RATIO
        )


    else:

        passed = False


    # ======================================================
    # Result
    # ======================================================

    return {

        "passed": (
            passed
        ),

        "combined_open_ratio": (
            combined_open_ratio
        ),

        "combined_closed_ratio": (
            combined_closed_ratio
        ),

        "combined_unknown_ratio": (
            combined_unknown_ratio
        ),

        "right_open_ratio": (
            right_open_ratio
        ),

        "right_closed_ratio": (
            right_closed_ratio
        ),

        "left_open_ratio": (
            left_open_ratio
        ),

        "left_closed_ratio": (
            left_closed_ratio
        ),
    }


# ==========================================================
# Print Calibration
# ==========================================================

def print_calibration_result(
    result
):

    print(
        "\n"
        "=============================================="
    )


    print(
        "OPEN-EYE CALIBRATION COMPLETE"
    )


    print(
        "=============================================="
    )


    print(
        "Samples:",
        result[
            "calibration_samples"
        ]
    )


    print(
        "\nRIGHT EYE"
    )


    print(
        "Open Reference:",
        f"{result['right_open_reference']:.5f}"
    )


    print(
        "Close Threshold:",
        f"{result['right_close_threshold']:.5f}"
    )


    print(
        "Reopen Threshold:",
        f"{result['right_reopen_threshold']:.5f}"
    )


    print(
        "\nLEFT EYE"
    )


    print(
        "Open Reference:",
        f"{result['left_open_reference']:.5f}"
    )


    print(
        "Close Threshold:",
        f"{result['left_close_threshold']:.5f}"
    )


    print(
        "Reopen Threshold:",
        f"{result['left_reopen_threshold']:.5f}"
    )


    print(
        "=============================================="
    )


# ==========================================================
# Print Capture Result
# ==========================================================

def print_capture_result(
    step,
    valid_samples,
    combined_counter,
    right_counter,
    left_counter,
    evaluation
):

    print(
        "\n"
        "=============================================="
    )


    print(
        "STATE TEST"
    )


    print(
        "State:",
        step[
            "state"
        ]
    )


    if (
        step[
            "round"
        ]
        >
        0
    ):

        print(
            "Round:",
            step[
                "round"
            ]
        )


    print(
        "Valid Samples:",
        valid_samples
    )


    print(
        "------------------------------------------------"
    )


    print(
        "COMBINED"
    )


    print(
        "OPEN:",
        combined_counter[
            EYE_OPEN
        ],
        (
            f"({evaluation['combined_open_ratio']:.1%})"
        )
    )


    print(
        "CLOSED:",
        combined_counter[
            EYE_CLOSED
        ],
        (
            f"({evaluation['combined_closed_ratio']:.1%})"
        )
    )


    print(
        "UNKNOWN:",
        combined_counter[
            EYE_UNKNOWN
        ],
        (
            f"({evaluation['combined_unknown_ratio']:.1%})"
        )
    )


    print(
        "\nRIGHT EYE"
    )


    print(
        "OPEN:",
        right_counter[
            EYE_OPEN
        ],
        (
            f"({evaluation['right_open_ratio']:.1%})"
        )
    )


    print(
        "CLOSED:",
        right_counter[
            EYE_CLOSED
        ],
        (
            f"({evaluation['right_closed_ratio']:.1%})"
        )
    )


    print(
        "\nLEFT EYE"
    )


    print(
        "OPEN:",
        left_counter[
            EYE_OPEN
        ],
        (
            f"({evaluation['left_open_ratio']:.1%})"
        )
    )


    print(
        "CLOSED:",
        left_counter[
            EYE_CLOSED
        ],
        (
            f"({evaluation['left_closed_ratio']:.1%})"
        )
    )


    print(
        "------------------------------------------------"
    )


    print(
        "RESULT:",
        (
            "PASS"
            if evaluation[
                "passed"
            ]
            else
            "FAIL"
        )
    )


    print(
        "=============================================="
    )


# ==========================================================
# Save CSV
# ==========================================================

def save_results(
    results,
    calibration_result
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
            "eye_state_validation_"
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
                "round",
                "state",
                "expected",
                "valid_samples",

                "combined_open_ratio",
                "combined_closed_ratio",
                "combined_unknown_ratio",

                "right_open_ratio",
                "right_closed_ratio",

                "left_open_ratio",
                "left_closed_ratio",

                "passed",

                "right_open_reference",
                "right_close_threshold",
                "right_reopen_threshold",

                "left_open_reference",
                "left_close_threshold",
                "left_reopen_threshold",
            ]
        )


        for item in results:

            evaluation = (
                item[
                    "evaluation"
                ]
            )


            writer.writerow(
                [
                    item[
                        "round"
                    ],

                    item[
                        "state"
                    ],

                    item[
                        "expected"
                    ],

                    item[
                        "valid_samples"
                    ],

                    evaluation[
                        "combined_open_ratio"
                    ],

                    evaluation[
                        "combined_closed_ratio"
                    ],

                    evaluation[
                        "combined_unknown_ratio"
                    ],

                    evaluation[
                        "right_open_ratio"
                    ],

                    evaluation[
                        "right_closed_ratio"
                    ],

                    evaluation[
                        "left_open_ratio"
                    ],

                    evaluation[
                        "left_closed_ratio"
                    ],

                    evaluation[
                        "passed"
                    ],

                    calibration_result[
                        "right_open_reference"
                    ],

                    calibration_result[
                        "right_close_threshold"
                    ],

                    calibration_result[
                        "right_reopen_threshold"
                    ],

                    calibration_result[
                        "left_open_reference"
                    ],

                    calibration_result[
                        "left_close_threshold"
                    ],

                    calibration_result[
                        "left_reopen_threshold"
                    ],
                ]
            )


    print(
        "\nResults saved:"
    )


    print(
        output_path
    )


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(
    results
):

    open_pass = 0

    open_total = 0


    closed_pass = 0

    closed_total = 0


    right_wink_pass = 0

    left_wink_pass = 0


    for item in results:

        expected = (
            item[
                "expected"
            ]
        )


        passed = (
            item[
                "evaluation"
            ][
                "passed"
            ]
        )


        if expected == "OPEN":

            open_total += 1


            if passed:

                open_pass += 1


        elif expected == "CLOSED":

            closed_total += 1


            if passed:

                closed_pass += 1


        elif expected == "RIGHT_WINK":

            if passed:

                right_wink_pass = 1


        elif expected == "LEFT_WINK":

            if passed:

                left_wink_pass = 1


    final_pass = (

        open_pass
        ==
        open_total

        and

        closed_pass
        ==
        closed_total

        and

        right_wink_pass
        ==
        1

        and

        left_wink_pass
        ==
        1
    )


    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD EYE STATE VALIDATION REPORT"
    )


    print(
        "################################################"
    )


    print(
        "OPEN State:",
        f"{open_pass}/{open_total}"
    )


    print(
        "CLOSED State:",
        f"{closed_pass}/{closed_total}"
    )


    print(
        "RIGHT Wink Rejection:",
        f"{right_wink_pass}/1"
    )


    print(
        "LEFT Wink Rejection:",
        f"{left_wink_pass}/1"
    )


    print(
        "------------------------------------------------"
    )


    if final_pass:

        print(
            "EYE STATE VALIDATION: PASS"
        )


        print(
            "Open-Eye Calibration + Hysteresis "
            "can be LOCKED for the prototype."
        )


    else:

        print(
            "EYE STATE VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Eye State yet."
        )


    print(
        "################################################"
    )


    return final_pass


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

            calibration_seconds=3.0,

            min_calibration_samples=30,

            close_factor=0.55,

            reopen_factor=0.70,
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

    test_index = 0


    results = []


    calibration_result = None

    calibration_report_printed = False


    preparing = False

    collecting = False


    prepare_started_at = None

    collection_started_at = None


    combined_counter = (
        make_state_counter()
    )


    right_counter = (
        make_state_counter()
    )


    left_counter = (
        make_state_counter()
    )


    valid_samples = 0


    test_complete = False


    status_message = (
        "Press C to start open-eye calibration"
    )


    # ======================================================
    # Instructions
    # ======================================================

    print(
        "\n"
        "==============================================\n"
        "POSTGUARD EYE STATE VALIDATION\n"
        "==============================================\n"
        "\n"
        "STEP 1:\n"
        "Press C and keep BOTH eyes naturally OPEN\n"
        "during 3-second calibration.\n"
        "\n"
        "After calibration:\n"
        "SPACE = capture current test state\n"
        "R     = reset calibration/test\n"
        "Q/ESC = quit\n"
        "==============================================\n"
    )


    # ======================================================
    # Loop
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
        # Face
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
        # Calibration Completed
        # ==================================================

        if (
            eye_state_result[
                "calibration_status"
            ]
            ==
            CALIBRATION_READY

            and

            not calibration_report_printed
        ):

            calibration_report_printed = True


            calibration_result = dict(
                eye_state_result
            )


            print_calibration_result(
                eye_state_result
            )


            status_message = (
                "Calibration READY - Press SPACE"
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
                PREPARE_DURATION_SECONDS
            ):

                preparing = False

                collecting = True


                collection_started_at = (
                    time.perf_counter()
                )


                combined_counter = (
                    make_state_counter()
                )


                right_counter = (
                    make_state_counter()
                )


                left_counter = (
                    make_state_counter()
                )


                valid_samples = 0


        # ==================================================
        # Collect State Samples
        # ==================================================

        if collecting:

            collection_elapsed = (
                time.perf_counter()
                -
                collection_started_at
            )


            if (
                eye_measurement
                is not None

                and

                eye_state_result[
                    "calibrated"
                ]
            ):

                combined_state = (
                    eye_state_result[
                        "eye_state"
                    ]
                )


                right_state = (
                    eye_state_result[
                        "right_eye_state"
                    ]
                )


                left_state = (
                    eye_state_result[
                        "left_eye_state"
                    ]
                )


                combined_counter[
                    combined_state
                ] += 1


                right_counter[
                    right_state
                ] += 1


                left_counter[
                    left_state
                ] += 1


                valid_samples += 1


            # ==============================================
            # Capture Done
            # ==============================================

            if (
                collection_elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                if (
                    valid_samples
                    <
                    MIN_VALID_SAMPLES
                ):

                    print(
                        "\nNot enough valid samples."
                    )


                    print(
                        "Retry current state."
                    )


                    status_message = (
                        "RETRY CURRENT STATE"
                    )


                else:

                    step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    evaluation = (
                        evaluate_capture(

                            step,

                            valid_samples,

                            combined_counter,

                            right_counter,

                            left_counter,
                        )
                    )


                    record = {

                        "round": (
                            step[
                                "round"
                            ]
                        ),

                        "state": (
                            step[
                                "state"
                            ]
                        ),

                        "expected": (
                            step[
                                "expected"
                            ]
                        ),

                        "valid_samples": (
                            valid_samples
                        ),

                        "evaluation": (
                            evaluation
                        ),
                    }


                    results.append(
                        record
                    )


                    print_capture_result(

                        step,

                        valid_samples,

                        combined_counter,

                        right_counter,

                        left_counter,

                        evaluation,
                    )


                    test_index += 1


                    if (
                        test_index
                        >=
                        len(
                            TEST_SEQUENCE
                        )
                    ):

                        test_complete = True


                        print_final_report(
                            results
                        )


                        if (
                            calibration_result
                            is not None
                        ):

                            save_results(
                                results,
                                calibration_result
                            )


                        status_message = (
                            "EYE STATE TEST COMPLETE"
                        )


                    else:

                        next_step = (
                            TEST_SEQUENCE[
                                test_index
                            ]
                        )


                        status_message = (
                            "Next: "
                            +
                            next_step[
                                "state"
                            ]
                        )


        # ==================================================
        # Display Frame
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
        # Calibration Display
        # ==================================================

        calibration_status = (
            eye_state_result[
                "calibration_status"
            ]
        )


        cv2.putText(
            display_frame,
            (
                "Calibration: "
                f"{calibration_status}"
            ),
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
        )


        if (
            calibration_status
            !=
            CALIBRATION_READY
        ):

            progress = int(
                eye_state_result[
                    "calibration_progress"
                ]
                *
                100
            )


            cv2.putText(
                display_frame,
                (
                    "Progress: "
                    f"{progress}%"
                ),
                (20, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1
            )


        # ==================================================
        # Openness
        # ==================================================

        if eye_measurement is not None:

            cv2.putText(
                display_frame,
                (
                    "Right Openness: "
                    f"{eye_measurement['right_eye_openness']:.4f}"
                ),
                (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


            cv2.putText(
                display_frame,
                (
                    "Left Openness: "
                    f"{eye_measurement['left_eye_openness']:.4f}"
                ),
                (20, 125),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1
            )


        # ==================================================
        # Eye State
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "RIGHT STATE: "
                f"{eye_state_result['right_eye_state']}"
            ),
            (20, 165),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            (
                "LEFT STATE: "
                f"{eye_state_result['left_eye_state']}"
            ),
            (20, 195),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            (
                "EYE STATE: "
                f"{eye_state_result['eye_state']}"
            ),
            (20, 230),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.70,
            (0, 255, 255),
            2
        )


        # ==================================================
        # Current Test
        # ==================================================

        if (
            eye_state_result[
                "calibrated"
            ]

            and

            not test_complete
        ):

            current_step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            cv2.putText(
                display_frame,
                (
                    "TEST: "
                    f"{current_step['state']}"
                ),
                (20, 275),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                get_instruction(
                    current_step[
                        "state"
                    ]
                ),
                (20, 305),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1
            )


        # ==================================================
        # Runtime
        # ==================================================

        if preparing:

            runtime_text = (
                "PREPARING..."
            )


        elif collecting:

            elapsed = (
                time.perf_counter()
                -
                collection_started_at
            )


            runtime_text = (
                "CAPTURING "
                f"{elapsed:.1f}/"
                f"{SAMPLE_DURATION_SECONDS:.1f}s "
                f"samples={valid_samples}"
            )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            runtime_text,
            (20, 340),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Controls
        # ==================================================

        cv2.putText(
            display_frame,
            "C=Calibrate  SPACE=Capture  R=Reset  Q=Quit",
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
            "PostGuard - Eye State Validation",
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
        # C = Start Calibration
        # ==================================================

        if key in (
            ord("c"),
            ord("C")
        ):

            eye_state_detector.start_calibration(
                timestamp=time.perf_counter()
            )


            calibration_report_printed = False

            calibration_result = None


            test_index = 0

            results = []

            test_complete = False


            preparing = False

            collecting = False


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
        # SPACE = Capture Current State
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

            and

            not test_complete
        ):

            step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            print(
                "\nPrepare:"
            )


            print(
                "State:",
                step[
                    "state"
                ]
            )


            print(
                get_instruction(
                    step[
                        "state"
                    ]
                )
            )


            preparing = True


            prepare_started_at = (
                time.perf_counter()
            )


            status_message = (
                "PREPARING"
            )


        # ==================================================
        # R = Full Reset
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            eye_state_detector.reset()


            test_index = 0

            results = []


            calibration_result = None

            calibration_report_printed = False


            preparing = False

            collecting = False


            test_complete = False


            status_message = (
                "RESET - Press C to calibrate"
            )


            print(
                "\nEye State Test RESET"
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