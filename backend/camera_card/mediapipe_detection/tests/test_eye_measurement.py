from pathlib import Path

import sys
import time
import csv
import math

from datetime import datetime


import cv2
import numpy as np


# ==========================================================
# Project Root
#
# tests/test_eye_measurement.py
#
# parents[2]
# = camera_card
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
# PostGuard Face Modules
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


from mediapipe_detection.face.face_validator import (
    validate_eye_points
)


from mediapipe_detection.eye.eye_measurement import (
    calculate_eye_openness
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

# หลังจากกด SPACE
# ให้เวลาจัดตาก่อนเริ่ม capture
PREPARE_DURATION_SECONDS = 1.5


# เก็บข้อมูลแต่ละ state
SAMPLE_DURATION_SECONDS = 2.0


# จำนวน sample ขั้นต่ำที่ยอมรับ
MIN_VALID_SAMPLES = 15


# ==========================================================
# Test Sequence
#
# 3 Rounds:
#
# OPEN_1
#    ↓
# CLOSED
#    ↓
# OPEN_2
#
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
            },

            {
                "round": round_number,
                "state": "CLOSED",
            },

            {
                "round": round_number,
                "state": "OPEN_2",
            },
        ]
    )


# ==========================================================
# Numeric Helper
# ==========================================================

def is_finite_number(
    value
):

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

def summarize_values(
    values
):

    values = np.asarray(
        values,
        dtype=np.float64
    )


    return {

        "median": float(
            np.median(
                values
            )
        ),

        "mean": float(
            np.mean(
                values
            )
        ),

        "std": float(
            np.std(
                values
            )
        ),

        "min": float(
            np.min(
                values
            )
        ),

        "max": float(
            np.max(
                values
            )
        ),
    }


# ==========================================================
# Instruction Text
# ==========================================================

def get_state_instruction(
    state
):

    if state.startswith(
        "OPEN"
    ):

        return (
            "LOOK STRAIGHT - KEEP BOTH EYES NATURALLY OPEN"
        )


    if state == "CLOSED":

        return (
            "CLOSE BOTH EYES NATURALLY"
        )


    return state


# ==========================================================
# Find Result by Round / State
# ==========================================================

def get_state_result(
    results,
    round_number,
    state
):

    for result in results:

        if (
            result[
                "round"
            ]
            ==
            round_number

            and

            result[
                "state"
            ]
            ==
            state
        ):

            return result


    return None


# ==========================================================
# Print Capture Summary
# ==========================================================

def print_state_result(
    step,
    summary
):

    print(
        "\n"
        "================================================"
    )


    print(
        f"ROUND: {step['round']}"
    )


    print(
        f"STATE: {step['state']}"
    )


    print(
        f"VALID SAMPLES: {summary['samples']}"
    )


    print(
        "------------------------------------------------"
    )


    print(
        "RIGHT EYE"
    )


    print(
        "  Median:",
        f"{summary['right']['median']:.5f}"
    )


    print(
        "  Mean  :",
        f"{summary['right']['mean']:.5f}"
    )


    print(
        "  Std   :",
        f"{summary['right']['std']:.5f}"
    )


    print(
        "  Min   :",
        f"{summary['right']['min']:.5f}"
    )


    print(
        "  Max   :",
        f"{summary['right']['max']:.5f}"
    )


    print(
        "\nLEFT EYE"
    )


    print(
        "  Median:",
        f"{summary['left']['median']:.5f}"
    )


    print(
        "  Mean  :",
        f"{summary['left']['mean']:.5f}"
    )


    print(
        "  Std   :",
        f"{summary['left']['std']:.5f}"
    )


    print(
        "  Min   :",
        f"{summary['left']['min']:.5f}"
    )


    print(
        "  Max   :",
        f"{summary['left']['max']:.5f}"
    )


    print(
        "\nMEAN BOTH EYES"
    )


    print(
        "  Median:",
        f"{summary['mean']['median']:.5f}"
    )


    print(
        "  Mean  :",
        f"{summary['mean']['mean']:.5f}"
    )


    print(
        "  Std   :",
        f"{summary['mean']['std']:.5f}"
    )


    print(
        "  Min   :",
        f"{summary['mean']['min']:.5f}"
    )


    print(
        "  Max   :",
        f"{summary['mean']['max']:.5f}"
    )


    print(
        "================================================"
    )


# ==========================================================
# Analyse 3 Rounds
# ==========================================================

def analyse_rounds(
    results
):

    reports = []


    for round_number in range(
        1,
        4
    ):

        open_1 = get_state_result(
            results,
            round_number,
            "OPEN_1"
        )


        closed = get_state_result(
            results,
            round_number,
            "CLOSED"
        )


        open_2 = get_state_result(
            results,
            round_number,
            "OPEN_2"
        )


        if any(
            item is None
            for item in (
                open_1,
                closed,
                open_2,
            )
        ):

            continue


        # ==================================================
        # Helper
        # ==================================================

        def median_value(
            record,
            side
        ):

            return (
                record[
                    "summary"
                ][
                    side
                ][
                    "median"
                ]
            )


        # ==================================================
        # RIGHT Eye
        # ==================================================

        right_open_1 = median_value(
            open_1,
            "right"
        )


        right_closed = median_value(
            closed,
            "right"
        )


        right_open_2 = median_value(
            open_2,
            "right"
        )


        right_close_delta = (
            right_closed
            -
            right_open_1
        )


        right_return_error = abs(
            right_open_2
            -
            right_open_1
        )


        right_response_pass = (
            right_close_delta
            <
            0
        )


        right_return_pass = (

            abs(
                right_close_delta
            )
            >
            0

            and

            right_return_error
            <
            abs(
                right_close_delta
            )
        )


        # ==================================================
        # LEFT Eye
        # ==================================================

        left_open_1 = median_value(
            open_1,
            "left"
        )


        left_closed = median_value(
            closed,
            "left"
        )


        left_open_2 = median_value(
            open_2,
            "left"
        )


        left_close_delta = (
            left_closed
            -
            left_open_1
        )


        left_return_error = abs(
            left_open_2
            -
            left_open_1
        )


        left_response_pass = (
            left_close_delta
            <
            0
        )


        left_return_pass = (

            abs(
                left_close_delta
            )
            >
            0

            and

            left_return_error
            <
            abs(
                left_close_delta
            )
        )


        # ==================================================
        # MEAN
        # ==================================================

        mean_open_1 = median_value(
            open_1,
            "mean"
        )


        mean_closed = median_value(
            closed,
            "mean"
        )


        mean_open_2 = median_value(
            open_2,
            "mean"
        )


        mean_close_delta = (
            mean_closed
            -
            mean_open_1
        )


        mean_return_error = abs(
            mean_open_2
            -
            mean_open_1
        )


        mean_response_pass = (
            mean_close_delta
            <
            0
        )


        mean_return_pass = (

            abs(
                mean_close_delta
            )
            >
            0

            and

            mean_return_error
            <
            abs(
                mean_close_delta
            )
        )


        # ==================================================
        # CLOSED / OPEN Fraction
        #
        # Diagnostic only
        #
        # ยังไม่ใช้เป็น Threshold
        # ==================================================

        if right_open_1 > 1e-9:

            right_closed_fraction = (
                right_closed
                /
                right_open_1
            )

        else:

            right_closed_fraction = None


        if left_open_1 > 1e-9:

            left_closed_fraction = (
                left_closed
                /
                left_open_1
            )

        else:

            left_closed_fraction = None


        if mean_open_1 > 1e-9:

            mean_closed_fraction = (
                mean_closed
                /
                mean_open_1
            )

        else:

            mean_closed_fraction = None


        # ==================================================
        # Overall Return
        # ==================================================

        open_return_pass = (

            right_return_pass
            and
            left_return_pass
            and
            mean_return_pass
        )


        reports.append(
            {

                "round": (
                    round_number
                ),

                # ------------------------------------------
                # RIGHT
                # ------------------------------------------

                "right_open_1": (
                    right_open_1
                ),

                "right_closed": (
                    right_closed
                ),

                "right_open_2": (
                    right_open_2
                ),

                "right_close_delta": (
                    right_close_delta
                ),

                "right_return_error": (
                    right_return_error
                ),

                "right_response_pass": (
                    right_response_pass
                ),

                "right_return_pass": (
                    right_return_pass
                ),

                "right_closed_fraction": (
                    right_closed_fraction
                ),


                # ------------------------------------------
                # LEFT
                # ------------------------------------------

                "left_open_1": (
                    left_open_1
                ),

                "left_closed": (
                    left_closed
                ),

                "left_open_2": (
                    left_open_2
                ),

                "left_close_delta": (
                    left_close_delta
                ),

                "left_return_error": (
                    left_return_error
                ),

                "left_response_pass": (
                    left_response_pass
                ),

                "left_return_pass": (
                    left_return_pass
                ),

                "left_closed_fraction": (
                    left_closed_fraction
                ),


                # ------------------------------------------
                # MEAN
                # ------------------------------------------

                "mean_open_1": (
                    mean_open_1
                ),

                "mean_closed": (
                    mean_closed
                ),

                "mean_open_2": (
                    mean_open_2
                ),

                "mean_close_delta": (
                    mean_close_delta
                ),

                "mean_return_error": (
                    mean_return_error
                ),

                "mean_response_pass": (
                    mean_response_pass
                ),

                "mean_return_pass": (
                    mean_return_pass
                ),

                "mean_closed_fraction": (
                    mean_closed_fraction
                ),


                "open_return_pass": (
                    open_return_pass
                ),
            }
        )


    return reports


# ==========================================================
# Final Validation Report
# ==========================================================

def print_final_report(
    results
):

    reports = analyse_rounds(
        results
    )


    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD EYE OPENNESS VALIDATION REPORT"
    )


    print(
        "################################################"
    )


    print(
        "\nExpected Convention:"
    )


    print(
        "OPEN   -> Eye Openness HIGHER"
    )


    print(
        "CLOSED -> Eye Openness LOWER"
    )


    if len(
        reports
    ) != 3:

        print(
            "\nERROR: Incomplete test data."
        )

        return False


    right_response_count = 0

    left_response_count = 0

    mean_response_count = 0

    return_count = 0


    # ======================================================
    # Print Each Round
    # ======================================================

    for report in reports:

        if report[
            "right_response_pass"
        ]:

            right_response_count += 1


        if report[
            "left_response_pass"
        ]:

            left_response_count += 1


        if report[
            "mean_response_pass"
        ]:

            mean_response_count += 1


        if report[
            "open_return_pass"
        ]:

            return_count += 1


        print(
            f"\nROUND {report['round']}"
        )


        print(
            "------------------------------------------------"
        )


        # ==================================================
        # RIGHT
        # ==================================================

        print(
            "\nRIGHT EYE"
        )


        print(
            "OPEN_1:",
            f"{report['right_open_1']:.5f}"
        )


        print(
            "CLOSED:",
            f"{report['right_closed']:.5f}"
        )


        print(
            "OPEN_2:",
            f"{report['right_open_2']:.5f}"
        )


        print(
            "Close Delta:",
            f"{report['right_close_delta']:+.5f}"
        )


        print(
            "Return Error:",
            f"{report['right_return_error']:.5f}"
        )


        if (
            report[
                "right_closed_fraction"
            ]
            is not None
        ):

            print(
                "Closed/Open Fraction:",
                f"{report['right_closed_fraction']:.3f}"
            )


        print(
            "Response:",
            (
                "PASS"
                if report[
                    "right_response_pass"
                ]
                else "FAIL"
            )
        )


        # ==================================================
        # LEFT
        # ==================================================

        print(
            "\nLEFT EYE"
        )


        print(
            "OPEN_1:",
            f"{report['left_open_1']:.5f}"
        )


        print(
            "CLOSED:",
            f"{report['left_closed']:.5f}"
        )


        print(
            "OPEN_2:",
            f"{report['left_open_2']:.5f}"
        )


        print(
            "Close Delta:",
            f"{report['left_close_delta']:+.5f}"
        )


        print(
            "Return Error:",
            f"{report['left_return_error']:.5f}"
        )


        if (
            report[
                "left_closed_fraction"
            ]
            is not None
        ):

            print(
                "Closed/Open Fraction:",
                f"{report['left_closed_fraction']:.3f}"
            )


        print(
            "Response:",
            (
                "PASS"
                if report[
                    "left_response_pass"
                ]
                else "FAIL"
            )
        )


        # ==================================================
        # MEAN
        # ==================================================

        print(
            "\nMEAN BOTH EYES"
        )


        print(
            "OPEN_1:",
            f"{report['mean_open_1']:.5f}"
        )


        print(
            "CLOSED:",
            f"{report['mean_closed']:.5f}"
        )


        print(
            "OPEN_2:",
            f"{report['mean_open_2']:.5f}"
        )


        print(
            "Close Delta:",
            f"{report['mean_close_delta']:+.5f}"
        )


        print(
            "Return Error:",
            f"{report['mean_return_error']:.5f}"
        )


        if (
            report[
                "mean_closed_fraction"
            ]
            is not None
        ):

            print(
                "Closed/Open Fraction:",
                f"{report['mean_closed_fraction']:.3f}"
            )


        print(
            "\nOpen Return:",
            (
                "PASS"
                if report[
                    "open_return_pass"
                ]
                else "FAIL"
            )
        )


    # ======================================================
    # Final Decision
    # ======================================================

    final_pass = (

        right_response_count
        ==
        3

        and

        left_response_count
        ==
        3

        and

        mean_response_count
        ==
        3

        and

        return_count
        ==
        3
    )


    print(
        "\n"
        "================================================"
    )


    print(
        "Right Eye Closure Response:",
        f"{right_response_count}/3"
    )


    print(
        "Left Eye Closure Response:",
        f"{left_response_count}/3"
    )


    print(
        "Mean Eye Closure Response:",
        f"{mean_response_count}/3"
    )


    print(
        "Open Return:",
        f"{return_count}/3"
    )


    print(
        "------------------------------------------------"
    )


    if final_pass:

        print(
            "EYE OPENNESS VALIDATION: PASS"
        )


        print(
            "Eye Openness Ratio can be LOCKED "
            "as a Validated Prototype Measurement."
        )


    else:

        print(
            "EYE OPENNESS VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Eye Openness Ratio yet."
        )


    print(
        "================================================"
    )


    return final_pass


# ==========================================================
# Save CSV
# ==========================================================

def save_results(
    results
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
            "eye_openness_validation_"
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
                "samples",

                "right_median",
                "right_mean",
                "right_std",
                "right_min",
                "right_max",

                "left_median",
                "left_mean",
                "left_std",
                "left_min",
                "left_max",

                "mean_median",
                "mean_mean",
                "mean_std",
                "mean_min",
                "mean_max",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            writer.writerow(
                [
                    result[
                        "round"
                    ],

                    result[
                        "state"
                    ],

                    summary[
                        "samples"
                    ],

                    summary[
                        "right"
                    ][
                        "median"
                    ],

                    summary[
                        "right"
                    ][
                        "mean"
                    ],

                    summary[
                        "right"
                    ][
                        "std"
                    ],

                    summary[
                        "right"
                    ][
                        "min"
                    ],

                    summary[
                        "right"
                    ][
                        "max"
                    ],

                    summary[
                        "left"
                    ][
                        "median"
                    ],

                    summary[
                        "left"
                    ][
                        "mean"
                    ],

                    summary[
                        "left"
                    ][
                        "std"
                    ],

                    summary[
                        "left"
                    ][
                        "min"
                    ],

                    summary[
                        "left"
                    ][
                        "max"
                    ],

                    summary[
                        "mean"
                    ][
                        "median"
                    ],

                    summary[
                        "mean"
                    ][
                        "mean"
                    ],

                    summary[
                        "mean"
                    ][
                        "std"
                    ],

                    summary[
                        "mean"
                    ][
                        "min"
                    ],

                    summary[
                        "mean"
                    ][
                        "max"
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
# Main
# ==========================================================

def main():

    # ======================================================
    # 1. Model Check
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
    # 2. Face Detector
    # ======================================================

    face_detector = (
        FaceDetector(
            FACE_MODEL_PATH
        )
    )


    # ======================================================
    # 3. Webcam
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


    # ======================================================
    # 4. Resolution
    # ======================================================

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )


    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )


    # ======================================================
    # Runtime Variables
    # ======================================================

    test_index = 0


    results = []


    preparing = False

    collecting = False


    prepare_started_at = None

    collection_started_at = None


    right_samples = []

    left_samples = []

    mean_samples = []


    test_complete = False

    results_saved = False


    status_message = (
        "Press SPACE to start current state"
    )


    print(
        "\n"
        "==============================================\n"
        "POSTGUARD EYE OPENNESS VALIDATION\n"
        "==============================================\n"
        "\n"
        "Sequence per round:\n"
        "OPEN_1 -> CLOSED -> OPEN_2\n"
        "\n"
        "Total: 3 rounds / 9 captures\n"
        "\n"
        "Controls:\n"
        "SPACE = start state capture\n"
        "R     = reset all test\n"
        "Q/ESC = quit\n"
        "==============================================\n"
    )


    # ======================================================
    # Main Loop
    # ======================================================

    while True:

        # ==================================================
        # Read RAW Frame
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


        # ==================================================
        # 5. Face Detection
        #
        # IMPORTANT:
        # Calculation ใช้ raw_frame
        # ไม่ใช้ mirror frame
        # ==================================================

        face_result = (
            face_detector.detect(
                raw_frame
            )
        )


        # ==================================================
        # 6. Extract Face Points
        # ==================================================

        face_points = (
            extract_face_points(
                face_result,
                frame_width,
                frame_height
            )
        )


        # ==================================================
        # 7. Validate Eye Points
        # ==================================================

        eye_validation = (
            validate_eye_points(
                face_points
            )
        )


        # ==================================================
        # 8. Calculate Eye Openness
        # ==================================================

        eye_result = None


        if eye_validation[
            "valid"
        ]:

            eye_result = (
                calculate_eye_openness(
                    face_points
                )
            )


        measurement_valid = (
            eye_result
            is not None
        )


        # ==================================================
        # PREPARE Phase
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


                right_samples = []

                left_samples = []

                mean_samples = []


        # ==================================================
        # COLLECT Phase
        # ==================================================

        if collecting:

            collection_elapsed = (
                time.perf_counter()
                -
                collection_started_at
            )


            # ==============================================
            # Valid measurement only
            # ==============================================

            if measurement_valid:

                right_value = (
                    eye_result[
                        "right_eye_openness"
                    ]
                )


                left_value = (
                    eye_result[
                        "left_eye_openness"
                    ]
                )


                mean_value = (
                    eye_result[
                        "mean_eye_openness"
                    ]
                )


                if (
                    is_finite_number(
                        right_value
                    )
                    and
                    is_finite_number(
                        left_value
                    )
                    and
                    is_finite_number(
                        mean_value
                    )
                ):

                    right_samples.append(
                        float(
                            right_value
                        )
                    )


                    left_samples.append(
                        float(
                            left_value
                        )
                    )


                    mean_samples.append(
                        float(
                            mean_value
                        )
                    )


            # ==============================================
            # Capture Finished
            # ==============================================

            if (
                collection_elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                valid_sample_count = min(
                    len(
                        right_samples
                    ),
                    len(
                        left_samples
                    ),
                    len(
                        mean_samples
                    ),
                )


                # ==========================================
                # Not Enough Samples
                # ==========================================

                if (
                    valid_sample_count
                    <
                    MIN_VALID_SAMPLES
                ):

                    print(
                        "\nNot enough valid eye samples."
                    )


                    print(
                        "Please retry current state."
                    )


                    status_message = (
                        "RETRY CURRENT STATE"
                    )


                # ==========================================
                # Successful Capture
                # ==========================================

                else:

                    current_step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    summary = {

                        "samples": (
                            valid_sample_count
                        ),

                        "right": (
                            summarize_values(
                                right_samples
                            )
                        ),

                        "left": (
                            summarize_values(
                                left_samples
                            )
                        ),

                        "mean": (
                            summarize_values(
                                mean_samples
                            )
                        ),
                    }


                    record = {

                        "round": (
                            current_step[
                                "round"
                            ]
                        ),

                        "state": (
                            current_step[
                                "state"
                            ]
                        ),

                        "summary": (
                            summary
                        ),
                    }


                    results.append(
                        record
                    )


                    print_state_result(
                        current_step,
                        summary
                    )


                    test_index += 1


                    # ======================================
                    # Test Complete
                    # ======================================

                    if (
                        test_index
                        >=
                        len(
                            TEST_SEQUENCE
                        )
                    ):

                        test_complete = True


                        final_pass = (
                            print_final_report(
                                results
                            )
                        )


                        if not results_saved:

                            save_results(
                                results
                            )


                            results_saved = True


                        if final_pass:

                            status_message = (
                                "EYE OPENNESS PASS"
                            )

                        else:

                            status_message = (
                                "EYE OPENNESS NEEDS REVIEW"
                            )


                    # ======================================
                    # Next State
                    # ======================================

                    else:

                        next_step = (
                            TEST_SEQUENCE[
                                test_index
                            ]
                        )


                        status_message = (
                            "Next: Round "
                            f"{next_step['round']} "
                            f"{next_step['state']}"
                        )


        # ==================================================
        # Mirror DISPLAY only
        # ==================================================

        display_frame = (
            cv2.flip(
                raw_frame,
                1
            )
        )


        # ==================================================
        # Draw Existing Face Points
        # ==================================================

        display_frame = (
            draw_face_points(
                display_frame,
                face_points,
                mirrored=True
            )
        )


        # ==================================================
        # Eye Measurement Display
        # ==================================================

        if measurement_valid:

            cv2.putText(
                display_frame,
                (
                    "Right Openness: "
                    f"{eye_result['right_eye_openness']:.4f}"
                ),
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Left Openness: "
                    f"{eye_result['left_eye_openness']:.4f}"
                ),
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Mean Openness: "
                    f"{eye_result['mean_eye_openness']:.4f}"
                ),
                (20, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Eye Measurement: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Current Test Step
        # ==================================================

        if not test_complete:

            current_step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            state_text = (
                f"Round "
                f"{current_step['round']}/3 "
                f"{current_step['state']}"
            )


            instruction = (
                get_state_instruction(
                    current_step[
                        "state"
                    ]
                )
            )


        else:

            state_text = (
                "EYE OPENNESS TEST COMPLETE"
            )


            instruction = (
                status_message
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            instruction,
            (20, 175),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.47,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Runtime Status
        # ==================================================

        if preparing:

            remaining = max(
                0.0,
                PREPARE_DURATION_SECONDS
                -
                (
                    time.perf_counter()
                    -
                    prepare_started_at
                )
            )


            runtime_text = (
                "PREPARE: "
                f"{remaining:.1f}s"
            )


        elif collecting:

            elapsed = min(
                SAMPLE_DURATION_SECONDS,
                (
                    time.perf_counter()
                    -
                    collection_started_at
                )
            )


            runtime_text = (
                "CAPTURING: "
                f"{elapsed:.1f}/"
                f"{SAMPLE_DURATION_SECONDS:.1f}s "
                f"samples={len(mean_samples)}"
            )


        else:

            runtime_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            runtime_text,
            (20, 210),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Controls
        # ==================================================

        cv2.putText(
            display_frame,
            "SPACE=Start  R=Reset  Q=Quit",
            (
                20,
                frame_height - 25
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Display
        # ==================================================

        cv2.imshow(
            "PostGuard - Eye Openness Validation",
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
        # SPACE = Start Current State
        # ==================================================

        if (
            key
            ==
            ord(" ")

            and

            not preparing

            and

            not collecting

            and

            not test_complete
        ):

            if not measurement_valid:

                print(
                    "Eye measurement INVALID."
                )


                status_message = (
                    "EYE POINTS INVALID"
                )


            else:

                current_step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print(
                    "\nPrepare capture:"
                )


                print(
                    "Round:",
                    current_step[
                        "round"
                    ]
                )


                print(
                    "State:",
                    current_step[
                        "state"
                    ]
                )


                print(
                    get_state_instruction(
                        current_step[
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
        # R = Reset
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            test_index = 0


            results = []


            preparing = False

            collecting = False


            prepare_started_at = None

            collection_started_at = None


            right_samples = []

            left_samples = []

            mean_samples = []


            test_complete = False

            results_saved = False


            status_message = (
                "RESET - Round 1 OPEN_1"
            )


            print(
                "\nEye Openness Test RESET"
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