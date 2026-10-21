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


# ==========================================================
# Measurement
# ==========================================================

from mediapipe_detection.posture.relative_distance import (
    calculate_eye_distance
)


# ==========================================================
# Face Model Path
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Test Settings
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# Test Sequence
#
# 3 Rounds:
#
# NORMAL_1
# MOVE_CLOSER
# NORMAL_2
# MOVE_FARTHER
# NORMAL_3
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
                "state": "NORMAL_1",
            },

            {
                "round": round_number,
                "state": "MOVE_CLOSER",
            },

            {
                "round": round_number,
                "state": "NORMAL_2",
            },

            {
                "round": round_number,
                "state": "MOVE_FARTHER",
            },

            {
                "round": round_number,
                "state": "NORMAL_3",
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
# Validate Required Face Points
# ==========================================================

def eye_points_valid(
    face_points
):

    if face_points is None:
        return False


    required_names = (
        "left_eye_outer",
        "left_eye_inner",
        "right_eye_inner",
        "right_eye_outer",
    )


    for point_name in required_names:

        if point_name not in face_points:
            return False


        point = face_points[
            point_name
        ]


        if point is None:
            return False


        if (
            "x" not in point
            or
            "y" not in point
        ):

            return False


        if (
            not is_finite_number(
                point["x"]
            )
            or
            not is_finite_number(
                point["y"]
            )
        ):

            return False


    return True


# ==========================================================
# Convert RAW Pixel Point -> Mirrored Display Point
#
# IMPORTANT:
#
# face_points x/y ของ PostGuard
# เป็น pixel coordinates อยู่แล้ว
#
# ไม่ต้องคูณ width / height ซ้ำ
# ==========================================================

def get_display_point(
    point,
    frame_width,
    mirrored=True
):

    x = int(
        round(
            point[0]
        )
    )

    y = int(
        round(
            point[1]
        )
    )


    if mirrored:

        x = (
            frame_width
            -
            1
            -
            x
        )


    return (
        x,
        y
    )


# ==========================================================
# Visualization
#
# Raw Measurement:
#
#     Left Eye Center ●--------------● Right Eye Center
#
#               eye_distance_px
#
# Visualization เท่านั้นที่ mirror
#
# Measurement คำนวณจาก RAW coordinates
# ==========================================================

def draw_eye_distance_debug(
    frame,
    eye_result,
    mirrored=True
):

    if eye_result is None:
        return frame


    frame_height, frame_width = (
        frame.shape[:2]
    )


    left_center = (
        eye_result[
            "left_eye_center"
        ]
    )


    right_center = (
        eye_result[
            "right_eye_center"
        ]
    )


    # ======================================================
    # Convert to DISPLAY coordinates
    # ======================================================

    left_display = get_display_point(
        left_center,
        frame_width,
        mirrored
    )


    right_display = get_display_point(
        right_center,
        frame_width,
        mirrored
    )


    # ======================================================
    # Inter-Eye Line
    # ======================================================

    cv2.line(
        frame,
        left_display,
        right_display,
        (0, 255, 255),
        3
    )


    # ======================================================
    # Eye Centers
    # ======================================================

    cv2.circle(
        frame,
        left_display,
        7,
        (0, 255, 255),
        -1
    )


    cv2.circle(
        frame,
        right_display,
        7,
        (0, 255, 255),
        -1
    )


    # ======================================================
    # Anatomical Labels
    # ======================================================

    cv2.putText(
        frame,
        "L CENTER",
        (
            left_display[0] - 40,
            left_display[1] - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 255),
        1
    )


    cv2.putText(
        frame,
        "R CENTER",
        (
            right_display[0] - 40,
            right_display[1] - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (0, 255, 255),
        1
    )


    # ======================================================
    # Measurement Value
    # ======================================================

    cv2.putText(
        frame,
        (
            "Eye Distance: "
            f"{eye_result['eye_distance_px']:.2f} px"
        ),
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (255, 255, 255),
        2
    )


    cv2.putText(
        frame,
        "Inter-Eye Distance / IPD Proxy",
        (20, 72),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (255, 255, 255),
        1
    )


    return frame


# ==========================================================
# Statistics
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
# Find State Result
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
# Print Captured State
# ==========================================================

def print_state_result(
    step,
    summary
):

    print(
        "\n"
        "=============================================="
    )


    print(
        "ROUND:",
        step[
            "round"
        ]
    )


    print(
        "STATE:",
        step[
            "state"
        ]
    )


    print(
        "VALID SAMPLES:",
        summary[
            "samples"
        ]
    )


    print(
        "----------------------------------------------"
    )


    print(
        "Inter-Eye Distance / IPD Proxy"
    )


    print(
        "  Median:",
        f"{summary['eye_distance']['median']:.3f} px"
    )


    print(
        "  Mean  :",
        f"{summary['eye_distance']['mean']:.3f} px"
    )


    print(
        "  Std   :",
        f"{summary['eye_distance']['std']:.3f} px"
    )


    print(
        "  Min   :",
        f"{summary['eye_distance']['min']:.3f} px"
    )


    print(
        "  Max   :",
        f"{summary['eye_distance']['max']:.3f} px"
    )


    print(
        "=============================================="
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

        normal_1 = get_state_result(
            results,
            round_number,
            "NORMAL_1"
        )


        closer = get_state_result(
            results,
            round_number,
            "MOVE_CLOSER"
        )


        normal_2 = get_state_result(
            results,
            round_number,
            "NORMAL_2"
        )


        farther = get_state_result(
            results,
            round_number,
            "MOVE_FARTHER"
        )


        normal_3 = get_state_result(
            results,
            round_number,
            "NORMAL_3"
        )


        # ==================================================
        # Check completeness
        # ==================================================

        if any(
            result is None
            for result in (
                normal_1,
                closer,
                normal_2,
                farther,
                normal_3,
            )
        ):

            continue


        # ==================================================
        # Median Helper
        # ==================================================

        def median(
            record
        ):

            return (
                record[
                    "summary"
                ][
                    "eye_distance"
                ][
                    "median"
                ]
            )


        # ==================================================
        # Standard Deviation Helper
        # ==================================================

        def std(
            record
        ):

            return (
                record[
                    "summary"
                ][
                    "eye_distance"
                ][
                    "std"
                ]
            )


        # ==================================================
        # Median Values
        # ==================================================

        normal_1_value = median(
            normal_1
        )


        closer_value = median(
            closer
        )


        normal_2_value = median(
            normal_2
        )


        farther_value = median(
            farther
        )


        normal_3_value = median(
            normal_3
        )


        # ==================================================
        # Delta
        #
        # Closer compares with NORMAL_1
        #
        # Farther compares with NORMAL_2
        # ==================================================

        closer_delta = (
            closer_value
            -
            normal_1_value
        )


        farther_delta = (
            farther_value
            -
            normal_2_value
        )


        # ==================================================
        # Expected Direction
        # ==================================================

        closer_direction_pass = (
            closer_delta > 0
        )


        farther_direction_pass = (
            farther_delta < 0
        )


        # ==================================================
        # Normal Return Error
        # ==================================================

        closer_return_error = abs(
            normal_2_value
            -
            normal_1_value
        )


        farther_return_error = abs(
            normal_3_value
            -
            normal_2_value
        )


        # ==================================================
        # Normal Return Prototype Check
        #
        # deliberate movement
        # ต้องเด่นกว่า normal drift
        #
        # ไม่ใช่ Risk Threshold
        # ==================================================

        closer_return_pass = (

            abs(
                closer_delta
            )
            >
            0

            and

            closer_return_error
            <
            abs(
                closer_delta
            )
        )


        farther_return_pass = (

            abs(
                farther_delta
            )
            >
            0

            and

            farther_return_error
            <
            abs(
                farther_delta
            )
        )


        normal_return_pass = (

            closer_return_pass

            and

            farther_return_pass
        )


        # ==================================================
        # Noise Diagnostics
        #
        # ไม่ใช้เป็น Risk threshold
        # ==================================================

        closer_noise = max(
            std(
                normal_1
            ),
            std(
                closer
            ),
            std(
                normal_2
            ),
        )


        farther_noise = max(
            std(
                normal_2
            ),
            std(
                farther
            ),
            std(
                normal_3
            ),
        )


        if closer_noise > 1e-9:

            closer_signal_noise = (
                abs(
                    closer_delta
                )
                /
                closer_noise
            )

        else:

            closer_signal_noise = (
                float("inf")
            )


        if farther_noise > 1e-9:

            farther_signal_noise = (
                abs(
                    farther_delta
                )
                /
                farther_noise
            )

        else:

            farther_signal_noise = (
                float("inf")
            )


        reports.append(
            {

                "round": (
                    round_number
                ),

                "normal_1": (
                    normal_1_value
                ),

                "closer": (
                    closer_value
                ),

                "normal_2": (
                    normal_2_value
                ),

                "farther": (
                    farther_value
                ),

                "normal_3": (
                    normal_3_value
                ),

                "closer_delta": (
                    closer_delta
                ),

                "farther_delta": (
                    farther_delta
                ),

                "closer_direction_pass": (
                    closer_direction_pass
                ),

                "farther_direction_pass": (
                    farther_direction_pass
                ),

                "closer_return_error": (
                    closer_return_error
                ),

                "farther_return_error": (
                    farther_return_error
                ),

                "closer_return_pass": (
                    closer_return_pass
                ),

                "farther_return_pass": (
                    farther_return_pass
                ),

                "normal_return_pass": (
                    normal_return_pass
                ),

                "closer_noise": (
                    closer_noise
                ),

                "farther_noise": (
                    farther_noise
                ),

                "closer_signal_noise": (
                    closer_signal_noise
                ),

                "farther_signal_noise": (
                    farther_signal_noise
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
        "POSTGUARD INTER-EYE DISTANCE VALIDATION REPORT"
    )


    print(
        "################################################"
    )


    if len(
        reports
    ) != 3:

        print(
            "ERROR: incomplete test data."
        )

        return False


    print(
        "\nExpected Measurement Convention"
    )


    print(
        "MOVE_CLOSER  -> INCREASE (+)"
    )


    print(
        "MOVE_FARTHER -> DECREASE (-)"
    )


    # ======================================================
    # Counters
    # ======================================================

    closer_direction_count = 0

    farther_direction_count = 0

    normal_return_count = 0


    # ======================================================
    # Each Round
    # ======================================================

    for report in reports:

        if report[
            "closer_direction_pass"
        ]:

            closer_direction_count += 1


        if report[
            "farther_direction_pass"
        ]:

            farther_direction_count += 1


        if report[
            "normal_return_pass"
        ]:

            normal_return_count += 1


        print(
            f"\nROUND {report['round']}"
        )


        print(
            "----------------------------------------------"
        )


        # ==================================================
        # Normal 1
        # ==================================================

        print(
            "NORMAL_1:"
        )


        print(
            f"  {report['normal_1']:.3f} px"
        )


        # ==================================================
        # Closer
        # ==================================================

        print(
            "\nMOVE_CLOSER:"
        )


        print(
            f"  {report['closer']:.3f} px"
        )


        print(
            "Closer Delta:"
        )


        print(
            f"  {report['closer_delta']:+.3f} px"
        )


        print(
            "Closer Direction:",
            (
                "PASS"
                if report[
                    "closer_direction_pass"
                ]
                else "FAIL"
            )
        )


        # ==================================================
        # Normal 2
        # ==================================================

        print(
            "\nNORMAL_2:"
        )


        print(
            f"  {report['normal_2']:.3f} px"
        )


        print(
            "Return Error After Closer:"
        )


        print(
            f"  {report['closer_return_error']:.3f} px"
        )


        # ==================================================
        # Farther
        # ==================================================

        print(
            "\nMOVE_FARTHER:"
        )


        print(
            f"  {report['farther']:.3f} px"
        )


        print(
            "Farther Delta:"
        )


        print(
            f"  {report['farther_delta']:+.3f} px"
        )


        print(
            "Farther Direction:",
            (
                "PASS"
                if report[
                    "farther_direction_pass"
                ]
                else "FAIL"
            )
        )


        # ==================================================
        # Normal 3
        # ==================================================

        print(
            "\nNORMAL_3:"
        )


        print(
            f"  {report['normal_3']:.3f} px"
        )


        print(
            "Return Error After Farther:"
        )


        print(
            f"  {report['farther_return_error']:.3f} px"
        )


        # ==================================================
        # Diagnostics
        # ==================================================

        print(
            "\nSignal / Noise Diagnostic"
        )


        if math.isfinite(
            report[
                "closer_signal_noise"
            ]
        ):

            print(
                "  Closer S/N:",
                f"{report['closer_signal_noise']:.3f}"
            )

        else:

            print(
                "  Closer S/N: INF"
            )


        if math.isfinite(
            report[
                "farther_signal_noise"
            ]
        ):

            print(
                "  Farther S/N:",
                f"{report['farther_signal_noise']:.3f}"
            )

        else:

            print(
                "  Farther S/N: INF"
            )


        # ==================================================
        # Normal Return
        # ==================================================

        print(
            "\nNormal Return:"
        )


        print(
            "  After Closer:",
            (
                "PASS"
                if report[
                    "closer_return_pass"
                ]
                else "FAIL"
            )
        )


        print(
            "  After Farther:",
            (
                "PASS"
                if report[
                    "farther_return_pass"
                ]
                else "FAIL"
            )
        )


        print(
            "  Overall:",
            (
                "PASS"
                if report[
                    "normal_return_pass"
                ]
                else "FAIL"
            )
        )


    # ======================================================
    # Final Prototype Measurement Result
    # ======================================================

    prototype_pass = (

        closer_direction_count
        ==
        3

        and

        farther_direction_count
        ==
        3

        and

        normal_return_count
        ==
        3
    )


    print(
        "\n"
        "================================================"
    )


    print(
        "Closer Direction Consistency:",
        f"{closer_direction_count}/3"
    )


    print(
        "Farther Direction Consistency:",
        f"{farther_direction_count}/3"
    )


    print(
        "Normal Return:",
        f"{normal_return_count}/3"
    )


    print(
        "------------------------------------------------"
    )


    if prototype_pass:

        print(
            "INTER-EYE DISTANCE VALIDATION: PASS"
        )


        print(
            "Inter-Eye Distance / IPD Proxy "
            "can be LOCKED as a "
            "Validated Prototype Measurement."
        )


    else:

        print(
            "INTER-EYE DISTANCE VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Inter-Eye Distance yet."
        )


    print(
        "================================================"
    )


    return prototype_pass


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
            "inter_eye_distance_validation_"
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
                "eye_distance_median_px",
                "eye_distance_mean_px",
                "eye_distance_std_px",
                "eye_distance_min_px",
                "eye_distance_max_px",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            eye_distance = (
                summary[
                    "eye_distance"
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

                    eye_distance[
                        "median"
                    ],

                    eye_distance[
                        "mean"
                    ],

                    eye_distance[
                        "std"
                    ],

                    eye_distance[
                        "min"
                    ],

                    eye_distance[
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

    face_detector = FaceDetector(
        FACE_MODEL_PATH
    )


    # ======================================================
    # Webcam
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
    # Runtime State
    # ======================================================

    test_index = 0

    results = []


    collecting = False

    collection_start = None

    samples = []


    test_complete = False

    results_saved = False


    status_message = (
        "Press SPACE to capture"
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
        # Face Detection
        #
        # IMPORTANT:
        # MediaPipe uses RAW frame
        # ==================================================

        face_result = (
            face_detector.detect(
                raw_frame
            )
        )


        # ==================================================
        # Selected Face Points
        # ==================================================

        face_points = (
            extract_face_points(
                face_result,
                frame_width,
                frame_height
            )
        )


        points_valid = (
            eye_points_valid(
                face_points
            )
        )


        # ==================================================
        # Calculate Inter-Eye Distance
        # ==================================================

        eye_result = None


        if points_valid:

            eye_result = (
                calculate_eye_distance(
                    face_points
                )
            )


        metric_valid = (
            eye_result
            is not None
        )


        # ==================================================
        # Capture
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                -
                collection_start
            )


            if metric_valid:

                samples.append(
                    float(
                        eye_result[
                            "eye_distance_px"
                        ]
                    )
                )


            # ==================================================
            # Capture Complete
            # ==================================================

            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ==========================================
                # Not Enough Valid Samples
                # ==========================================

                if (
                    len(
                        samples
                    )
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


                    samples = []


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

                        "samples": len(
                            samples
                        ),

                        "eye_distance": (
                            summarize_values(
                                samples
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


                    samples = []

                    test_index += 1


                    # ======================================
                    # Finished All 15 States
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
                                "INTER-EYE DISTANCE PASS"
                            )


                        else:

                            status_message = (
                                "INTER-EYE DISTANCE NEEDS REVIEW"
                            )


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
        # DISPLAY ONLY
        #
        # Mirror หลังจาก calculation
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # Draw Existing Face Landmarks
        # ==================================================

        if face_points is not None:

            display_frame = (
                draw_face_points(
                    display_frame,
                    face_points,
                    mirrored=True
                )
            )


        # ==================================================
        # Eye Distance Visualization
        # ==================================================

        if metric_valid:

            draw_eye_distance_debug(
                display_frame,
                eye_result,
                mirrored=True
            )


        else:

            cv2.putText(
                display_frame,
                "Inter-Eye Distance: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Face Status
        # ==================================================

        face_found = (

            face_result is not None

            and

            bool(
                face_result.face_landmarks
            )
        )


        cv2.putText(
            display_frame,
            (
                "Face: OK"
                if face_found
                else "Face: NOT FOUND"
            ),
            (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (
                (0, 255, 0)
                if face_found
                else (0, 0, 255)
            ),
            2
        )


        # ==================================================
        # Current Test State
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


            progress_text = (
                f"State "
                f"{test_index + 1}/"
                f"{len(TEST_SEQUENCE)}"
            )


        else:

            state_text = (
                "INTER-EYE DISTANCE TEST COMPLETE"
            )


            progress_text = (
                "All states completed"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            progress_text,
            (20, 175),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Capture Status
        # ==================================================

        if collecting:

            elapsed = min(
                (
                    time.perf_counter()
                    -
                    collection_start
                ),
                SAMPLE_DURATION_SECONDS
            )


            status = (
                "CAPTURING "
                f"{elapsed:.1f}/2.0 "
                f"samples={len(samples)}"
            )


        else:

            status = (
                status_message
            )


        cv2.putText(
            display_frame,
            status,
            (20, 205),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            2
        )


        # ==================================================
        # Controls
        # ==================================================

        cv2.putText(
            display_frame,
            "SPACE=Capture  R=Reset  Q=Quit",
            (
                20,
                frame_height - 30
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1
        )


        # ==================================================
        # Show
        # ==================================================

        cv2.imshow(
            "PostGuard - Inter-Eye Distance Validation",
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
        # SPACE = Capture
        # ==================================================

        if (
            key
            ==
            ord(" ")

            and

            not collecting

            and

            not test_complete
        ):

            if not metric_valid:

                print(
                    "Inter-Eye Distance INVALID"
                )


            else:

                current_step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print(
                    "\nStart capture:"
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


                collecting = True


                collection_start = (
                    time.perf_counter()
                )


                samples = []


        # ==================================================
        # R = Reset
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            test_index = 0

            results = []


            collecting = False

            collection_start = None

            samples = []


            test_complete = False

            results_saved = False


            status_message = (
                "RESET - Round 1 NORMAL_1"
            )


            print(
                "\nInter-Eye Distance Test RESET"
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