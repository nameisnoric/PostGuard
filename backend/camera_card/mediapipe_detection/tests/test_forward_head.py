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
# PostGuard Modules
# ==========================================================

from mediapipe_detection.pose.pose_detector import (
    PoseDetector
)


from mediapipe_detection.posture.posture_features import (
    calculate_forward_head
)


# ==========================================================
# Model Path
# ==========================================================

POSE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "pose_landmarker_lite.task"
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
# FORWARD_HEAD
# NORMAL_2
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
                "state": "FORWARD_HEAD",
            },

            {
                "round": round_number,
                "state": "NORMAL_2",
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
# Validate Required Pose Points
#
# Need:
#
# nose
# left_shoulder
# right_shoulder
#
# Both image x/y and world x/y/z
# ==========================================================

def forward_head_points_valid(
    points
):

    if points is None:
        return False


    required_points = (
        "nose",
        "left_shoulder",
        "right_shoulder",
    )


    required_values = (
        "x",
        "y",
        "world_x",
        "world_y",
        "world_z",
    )


    for point_name in required_points:

        if point_name not in points:
            return False


        point = points[
            point_name
        ]


        if point is None:
            return False


        for value_name in required_values:

            if value_name not in point:
                return False


            if not is_finite_number(
                point[
                    value_name
                ]
            ):
                return False


    return True


# ==========================================================
# Convert RAW point to mirrored DISPLAY point
#
# IMPORTANT:
#
# points["x"] / ["y"] in this PostGuard pipeline
# are already pixel coordinates.
#
# Do NOT multiply frame width/height again.
# ==========================================================

def get_display_point(
    point,
    frame_width,
    mirrored=True
):

    x = int(
        point["x"]
    )

    y = int(
        point["y"]
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
#               Nose
#                ●
#                |
#                |
#        Shoulder Midpoint
#                ●
#              /   \
#             /     \
#      Left ●---------● Right
#
#
# NOTE:
# Lines are for visual verification only.
#
# Forward Head metric itself uses WORLD Z,
# not these 2D lines.
# ==========================================================

def draw_forward_head_debug(
    frame,
    points,
    result,
    mirrored=True,
):

    if not forward_head_points_valid(
        points
    ):

        return frame


    if result is None:
        return frame


    frame_height, frame_width = (
        frame.shape[:2]
    )


    # ======================================================
    # Display coordinates
    # ======================================================

    nose = get_display_point(
        points[
            "nose"
        ],
        frame_width,
        mirrored
    )


    left_shoulder = get_display_point(
        points[
            "left_shoulder"
        ],
        frame_width,
        mirrored
    )


    right_shoulder = get_display_point(
        points[
            "right_shoulder"
        ],
        frame_width,
        mirrored
    )


    # ======================================================
    # Shoulder midpoint for visualization
    # ======================================================

    shoulder_mid = (

        int(
            (
                left_shoulder[0]
                +
                right_shoulder[0]
            )
            /
            2
        ),

        int(
            (
                left_shoulder[1]
                +
                right_shoulder[1]
            )
            /
            2
        ),
    )


    # ======================================================
    # Shoulder Line
    # ======================================================

    cv2.line(
        frame,
        left_shoulder,
        right_shoulder,
        (0, 255, 255),
        3
    )


    # ======================================================
    # Nose -> Shoulder Midpoint
    #
    # Visual guide only.
    # It does NOT represent Z depth.
    # ======================================================

    cv2.line(
        frame,
        nose,
        shoulder_mid,
        (255, 255, 255),
        2
    )


    # ======================================================
    # Optional Nose -> Each Shoulder
    # ======================================================

    cv2.line(
        frame,
        nose,
        left_shoulder,
        (150, 150, 150),
        1
    )


    cv2.line(
        frame,
        nose,
        right_shoulder,
        (150, 150, 150),
        1
    )


    # ======================================================
    # Points
    # ======================================================

    cv2.circle(
        frame,
        nose,
        8,
        (0, 255, 0),
        -1
    )


    cv2.circle(
        frame,
        left_shoulder,
        8,
        (0, 255, 0),
        -1
    )


    cv2.circle(
        frame,
        right_shoulder,
        8,
        (0, 255, 0),
        -1
    )


    cv2.circle(
        frame,
        shoulder_mid,
        7,
        (255, 255, 255),
        -1
    )


    # ======================================================
    # Labels
    # ======================================================

    cv2.putText(
        frame,
        "N",
        (
            nose[0] - 10,
            nose[1] - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (0, 255, 0),
        2
    )


    cv2.putText(
        frame,
        "L",
        (
            left_shoulder[0] - 10,
            left_shoulder[1] - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (0, 255, 0),
        2
    )


    cv2.putText(
        frame,
        "R",
        (
            right_shoulder[0] - 10,
            right_shoulder[1] - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (0, 255, 0),
        2
    )


    cv2.putText(
        frame,
        "MID",
        (
            shoulder_mid[0] + 10,
            shoulder_mid[1]
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.50,
        (255, 255, 255),
        1
    )


    # ======================================================
    # Forward Head Metric
    # ======================================================

    cv2.putText(
        frame,
        (
            "Forward Head: "
            f"{result['forward_head']:+.4f}"
        ),
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (255, 255, 255),
        2
    )


    # ======================================================
    # Diagnostic World Z Values
    # ======================================================

    cv2.putText(
        frame,
        (
            "Nose Z: "
            f"{result['nose_z']:+.4f}"
        ),
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        1
    )


    cv2.putText(
        frame,
        (
            "Shoulder Mid Z: "
            f"{result['shoulder_mid_z']:+.4f}"
        ),
        (20, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        1
    )


    cv2.putText(
        frame,
        (
            "Shoulder Width: "
            f"{result['shoulder_width']:.4f}"
        ),
        (20, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
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
# Get State Result
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
# Sign
# ==========================================================

def get_sign(
    value
):

    if value > 0:
        return 1

    if value < 0:
        return -1

    return 0


def sign_text(
    value
):

    if value > 0:
        return "POSITIVE (+)"

    if value < 0:
        return "NEGATIVE (-)"

    return "ZERO"


# ==========================================================
# Print State Capture
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
        "Forward Head"
    )


    print(
        "  Median:",
        f"{summary['forward_head']['median']:+.4f}"
    )


    print(
        "  Mean  :",
        f"{summary['forward_head']['mean']:+.4f}"
    )


    print(
        "  Std   :",
        f"{summary['forward_head']['std']:.4f}"
    )


    print(
        "----------------------------------------------"
    )


    print(
        "Nose Z Median:",
        f"{summary['nose_z']['median']:+.4f}"
    )


    print(
        "Shoulder Mid Z Median:",
        f"{summary['shoulder_mid_z']['median']:+.4f}"
    )


    print(
        "Shoulder Width Median:",
        f"{summary['shoulder_width']['median']:.4f}"
    )


    print(
        "=============================================="
    )


# ==========================================================
# Analyse Three Rounds
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


        forward = get_state_result(
            results,
            round_number,
            "FORWARD_HEAD"
        )


        normal_2 = get_state_result(
            results,
            round_number,
            "NORMAL_2"
        )


        if (
            normal_1 is None
            or forward is None
            or normal_2 is None
        ):

            continue


        # ==================================================
        # Median Values
        # ==================================================

        normal_1_value = (
            normal_1[
                "summary"
            ][
                "forward_head"
            ][
                "median"
            ]
        )


        forward_value = (
            forward[
                "summary"
            ][
                "forward_head"
            ][
                "median"
            ]
        )


        normal_2_value = (
            normal_2[
                "summary"
            ][
                "forward_head"
            ][
                "median"
            ]
        )


        # ==================================================
        # Standard Deviation
        # ==================================================

        normal_1_std = (
            normal_1[
                "summary"
            ][
                "forward_head"
            ][
                "std"
            ]
        )


        forward_std = (
            forward[
                "summary"
            ][
                "forward_head"
            ][
                "std"
            ]
        )


        normal_2_std = (
            normal_2[
                "summary"
            ][
                "forward_head"
            ][
                "std"
            ]
        )


        # ==================================================
        # Forward Head Delta
        #
        # Forward state uses preceding NORMAL_1
        # as experimental reference.
        #
        # NOT Personal Baseline.
        # ==================================================

        forward_delta = (
            forward_value
            -
            normal_1_value
        )


        # ==================================================
        # Normal Return Error
        # ==================================================

        return_error = abs(
            normal_2_value
            -
            normal_1_value
        )


        # ==================================================
        # Noise estimate
        #
        # No clinical threshold.
        #
        # Used only to check whether deliberate movement
        # is larger than frame-to-frame variation.
        # ==================================================

        noise_level = max(
            normal_1_std,
            forward_std,
            normal_2_std,
        )


        # ==================================================
        # Response check
        #
        # Movement should be larger than:
        #
        # 1. normal return drift
        # 2. state variation / noise
        #
        # This is NOT a risk threshold.
        # ==================================================

        response_pass = (

            abs(
                forward_delta
            )
            >
            return_error

            and

            abs(
                forward_delta
            )
            >
            noise_level
        )


        # ==================================================
        # Normal Return
        # ==================================================

        normal_return_pass = (

            abs(
                forward_delta
            )
            >
            0

            and

            return_error
            <
            abs(
                forward_delta
            )
        )


        # ==================================================
        # Signal-to-noise diagnostic
        # ==================================================

        if noise_level > 1e-9:

            signal_noise_ratio = (
                abs(
                    forward_delta
                )
                /
                noise_level
            )

        else:

            signal_noise_ratio = (
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

                "forward": (
                    forward_value
                ),

                "normal_2": (
                    normal_2_value
                ),

                "forward_delta": (
                    forward_delta
                ),

                "direction": (
                    get_sign(
                        forward_delta
                    )
                ),

                "return_error": (
                    return_error
                ),

                "noise_level": (
                    noise_level
                ),

                "signal_noise_ratio": (
                    signal_noise_ratio
                ),

                "response_pass": (
                    response_pass
                ),

                "normal_return_pass": (
                    normal_return_pass
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
        "POSTGUARD FORWARD HEAD VALIDATION REPORT"
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


    # ======================================================
    # Learn sign convention from Round 1
    # ======================================================

    expected_direction = (
        reports[0][
            "direction"
        ]
    )


    print(
        "\nObserved Forward Head Convention:"
    )


    print(
        sign_text(
            expected_direction
        )
    )


    response_count = 0

    direction_count = 0

    normal_return_count = 0


    # ======================================================
    # Print Each Round
    # ======================================================

    for report in reports:

        direction_consistent = (

            report[
                "direction"
            ]
            ==
            expected_direction

            and

            report[
                "direction"
            ]
            !=
            0
        )


        if report[
            "response_pass"
        ]:

            response_count += 1


        if direction_consistent:

            direction_count += 1


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


        print(
            "NORMAL_1:"
        )


        print(
            f"  {report['normal_1']:+.4f}"
        )


        print(
            "FORWARD_HEAD:"
        )


        print(
            f"  {report['forward']:+.4f}"
        )


        print(
            "Forward Head Delta:"
        )


        print(
            f"  {report['forward_delta']:+.4f}"
        )


        print(
            "NORMAL_2:"
        )


        print(
            f"  {report['normal_2']:+.4f}"
        )


        print(
            "Return Error:"
        )


        print(
            f"  {report['return_error']:.4f}"
        )


        print(
            "Noise Level:"
        )


        print(
            f"  {report['noise_level']:.4f}"
        )


        print(
            "Signal / Noise:"
        )


        if math.isfinite(
            report[
                "signal_noise_ratio"
            ]
        ):

            print(
                f"  {report['signal_noise_ratio']:.3f}"
            )


        else:

            print(
                "  INF"
            )


        print(
            "Forward Head Response:",
            (
                "PASS"
                if report[
                    "response_pass"
                ]
                else "FAIL"
            )
        )


        print(
            "Direction Consistency:",
            (
                "PASS"
                if direction_consistent
                else "FAIL"
            )
        )


        print(
            "Normal Return:",
            (
                "PASS"
                if report[
                    "normal_return_pass"
                ]
                else "FAIL"
            )
        )


    # ======================================================
    # Final Prototype Validation
    # ======================================================

    prototype_pass = (

        expected_direction
        !=
        0

        and

        response_count
        ==
        3

        and

        direction_count
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
        "Forward Head Response:",
        f"{response_count}/3"
    )


    print(
        "Direction Consistency:",
        f"{direction_count}/3"
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
            "FORWARD HEAD VALIDATION: PASS"
        )


        print(
            "Forward Head can be LOCKED as a "
            "Validated Prototype Metric."
        )


    else:

        print(
            "FORWARD HEAD VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Forward Head yet."
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
            "forward_head_validation_"
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

                "forward_head_median",
                "forward_head_mean",
                "forward_head_std",
                "forward_head_min",
                "forward_head_max",

                "nose_z_median",
                "shoulder_mid_z_median",
                "shoulder_width_median",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            forward_head = (
                summary[
                    "forward_head"
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

                    forward_head[
                        "median"
                    ],

                    forward_head[
                        "mean"
                    ],

                    forward_head[
                        "std"
                    ],

                    forward_head[
                        "min"
                    ],

                    forward_head[
                        "max"
                    ],

                    summary[
                        "nose_z"
                    ][
                        "median"
                    ],

                    summary[
                        "shoulder_mid_z"
                    ][
                        "median"
                    ],

                    summary[
                        "shoulder_width"
                    ][
                        "median"
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
    # Model Validation
    # ======================================================

    if not POSE_MODEL_PATH.exists():

        print(
            "Pose model not found:"
        )

        print(
            POSE_MODEL_PATH
        )

        return


    # ======================================================
    # Pose Detector
    # ======================================================

    pose_detector = PoseDetector(
        POSE_MODEL_PATH
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

        pose_detector.close()

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
    # Main Camera Loop
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
        # Pose Detection
        #
        # Always detect from RAW frame
        # ==================================================

        pose_points = (
            pose_detector.detect(
                raw_frame
            )
        )


        points_valid = (
            forward_head_points_valid(
                pose_points
            )
        )


        # ==================================================
        # Calculate Forward Head
        # ==================================================

        forward_head_result = None


        if points_valid:

            forward_head_result = (
                calculate_forward_head(

                    nose=(
                        pose_points[
                            "nose"
                        ]
                    ),

                    left_shoulder=(
                        pose_points[
                            "left_shoulder"
                        ]
                    ),

                    right_shoulder=(
                        pose_points[
                            "right_shoulder"
                        ]
                    ),
                )
            )


        metric_valid = (
            forward_head_result
            is not None
        )


        # ==================================================
        # Capture Samples
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                -
                collection_start
            )


            if metric_valid:

                samples.append(
                    {

                        "forward_head": (
                            forward_head_result[
                                "forward_head"
                            ]
                        ),

                        "nose_z": (
                            forward_head_result[
                                "nose_z"
                            ]
                        ),

                        "shoulder_mid_z": (
                            forward_head_result[
                                "shoulder_mid_z"
                            ]
                        ),

                        "shoulder_width": (
                            forward_head_result[
                                "shoulder_width"
                            ]
                        ),
                    }
                )


            # ==================================================
            # End Capture
            # ==================================================

            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ==========================================
                # Not enough samples
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
                # Successful capture
                # ==========================================

                else:

                    current_step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    forward_values = [
                        sample[
                            "forward_head"
                        ]
                        for sample
                        in samples
                    ]


                    nose_z_values = [
                        sample[
                            "nose_z"
                        ]
                        for sample
                        in samples
                    ]


                    shoulder_mid_z_values = [
                        sample[
                            "shoulder_mid_z"
                        ]
                        for sample
                        in samples
                    ]


                    shoulder_width_values = [
                        sample[
                            "shoulder_width"
                        ]
                        for sample
                        in samples
                    ]


                    summary = {

                        "samples": len(
                            samples
                        ),

                        "forward_head": (
                            summarize_values(
                                forward_values
                            )
                        ),

                        "nose_z": (
                            summarize_values(
                                nose_z_values
                            )
                        ),

                        "shoulder_mid_z": (
                            summarize_values(
                                shoulder_mid_z_values
                            )
                        ),

                        "shoulder_width": (
                            summarize_values(
                                shoulder_width_values
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
                                "FORWARD HEAD PASS"
                            )


                        else:

                            status_message = (
                                "FORWARD HEAD NEEDS REVIEW"
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
        # MIRROR DISPLAY ONLY
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # Visualization
        # ==================================================

        if metric_valid:

            draw_forward_head_debug(

                frame=(
                    display_frame
                ),

                points=(
                    pose_points
                ),

                result=(
                    forward_head_result
                ),

                mirrored=True,
            )


        else:

            cv2.putText(
                display_frame,
                "Forward Head: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 0, 255),
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
                "FORWARD HEAD TEST COMPLETE"
            )


            progress_text = (
                "All states completed"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 165),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            progress_text,
            (20, 195),
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
            (20, 225),
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
        # Window
        # ==================================================

        cv2.imshow(
            "PostGuard - Forward Head Validation",
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
                    "Forward Head INVALID"
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
                "\nForward Head Test RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()

    pose_detector.close()

    cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()