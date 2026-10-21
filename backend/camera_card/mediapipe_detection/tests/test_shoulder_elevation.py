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
    calculate_shoulder_elevation
)


# ==========================================================
# Model
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
# 7 states x 3 rounds
#
# NORMAL_1
# RAISE_LEFT
# NORMAL_2
# RAISE_RIGHT
# NORMAL_3
# RAISE_BOTH
# NORMAL_4
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
                "state": "RAISE_LEFT",
            },

            {
                "round": round_number,
                "state": "NORMAL_2",
            },

            {
                "round": round_number,
                "state": "RAISE_RIGHT",
            },

            {
                "round": round_number,
                "state": "NORMAL_3",
            },

            {
                "round": round_number,
                "state": "RAISE_BOTH",
            },

            {
                "round": round_number,
                "state": "NORMAL_4",
            },
        ]
    )


# ==========================================================
# Utility
# ==========================================================

def is_finite_number(value):

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
# Validate Required Landmarks
#
# Shoulder Elevation ใช้:
#
# - Nose
# - Left Shoulder
# - Right Shoulder
# ==========================================================

def elevation_points_valid(
    points
):

    if points is None:
        return False


    required_points = (
        "nose",
        "left_shoulder",
        "right_shoulder",
    )


    for name in required_points:

        if name not in points:
            return False


        point = points[name]


        if (
            "x" not in point
            or
            "y" not in point
        ):

            return False


        if not is_finite_number(
            point["x"]
        ):

            return False


        if not is_finite_number(
            point["y"]
        ):

            return False


    return True


# ==========================================================
# Convert point for mirrored DISPLAY only
#
# IMPORTANT:
# คำนวณ metric จาก raw landmark เหมือนเดิม
# mirror เฉพาะตอนวาด
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
#             Nose
#               ●
#              / \
#             /   \
#      L ●----------● R
#
# แสดง:
#
# - Nose
# - Left Shoulder
# - Right Shoulder
# - Nose -> Left Shoulder
# - Nose -> Right Shoulder
# - Shoulder Line
# - Left Elevation
# - Right Elevation
# ==========================================================

def draw_shoulder_elevation_debug(
    frame,
    points,
    left_elevation,
    right_elevation,
    mirrored=True,
):

    if not elevation_points_valid(
        points
    ):

        return frame


    frame_height, frame_width = (
        frame.shape[:2]
    )


    # ======================================================
    # Get Display Coordinates
    # ======================================================

    nose = get_display_point(
        points["nose"],
        frame_width,
        mirrored
    )


    left_shoulder = get_display_point(
        points["left_shoulder"],
        frame_width,
        mirrored
    )


    right_shoulder = get_display_point(
        points["right_shoulder"],
        frame_width,
        mirrored
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
    # Nose -> Left Shoulder
    # ======================================================

    cv2.line(
        frame,
        nose,
        left_shoulder,
        (255, 255, 255),
        2
    )


    # ======================================================
    # Nose -> Right Shoulder
    # ======================================================

    cv2.line(
        frame,
        nose,
        right_shoulder,
        (255, 255, 255),
        2
    )


    # ======================================================
    # Points
    # ======================================================

    cv2.circle(
        frame,
        nose,
        7,
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


    # ======================================================
    # Labels
    #
    # L / R = anatomical left/right
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


    # ======================================================
    # Metric Values
    # ======================================================

    cv2.putText(
        frame,
        (
            "Left Elevation : "
            f"{left_elevation:+.4f}"
        ),
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2
    )


    cv2.putText(
        frame,
        (
            "Right Elevation: "
            f"{right_elevation:+.4f}"
        ),
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2
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


def summarize_samples(
    samples
):

    left_values = [
        sample["left"]
        for sample in samples
    ]


    right_values = [
        sample["right"]
        for sample in samples
    ]


    return {

        "samples": len(
            samples
        ),

        "left": summarize_values(
            left_values
        ),

        "right": summarize_values(
            right_values
        ),
    }


# ==========================================================
# Find Result
# ==========================================================

def get_state_result(
    results,
    round_number,
    state
):

    for result in results:

        if (
            result["round"]
            ==
            round_number

            and

            result["state"]
            ==
            state
        ):

            return result


    return None


# ==========================================================
# Sign Helpers
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
        step["round"]
    )


    print(
        "STATE:",
        step["state"]
    )


    print(
        "VALID SAMPLES:",
        summary["samples"]
    )


    print(
        "----------------------------------------------"
    )


    print(
        "Left Shoulder Elevation"
    )


    print(
        "  Median:",
        f"{summary['left']['median']:+.4f}"
    )


    print(
        "  Mean  :",
        f"{summary['left']['mean']:+.4f}"
    )


    print(
        "  Std   :",
        f"{summary['left']['std']:.4f}"
    )


    print(
        "Right Shoulder Elevation"
    )


    print(
        "  Median:",
        f"{summary['right']['median']:+.4f}"
    )


    print(
        "  Mean  :",
        f"{summary['right']['mean']:+.4f}"
    )


    print(
        "  Std   :",
        f"{summary['right']['std']:.4f}"
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


        raise_left = get_state_result(
            results,
            round_number,
            "RAISE_LEFT"
        )


        normal_2 = get_state_result(
            results,
            round_number,
            "NORMAL_2"
        )


        raise_right = get_state_result(
            results,
            round_number,
            "RAISE_RIGHT"
        )


        normal_3 = get_state_result(
            results,
            round_number,
            "NORMAL_3"
        )


        raise_both = get_state_result(
            results,
            round_number,
            "RAISE_BOTH"
        )


        normal_4 = get_state_result(
            results,
            round_number,
            "NORMAL_4"
        )


        if any(
            result is None
            for result in (
                normal_1,
                raise_left,
                normal_2,
                raise_right,
                normal_3,
                raise_both,
                normal_4,
            )
        ):

            continue


        # ==================================================
        # Median Helper
        # ==================================================

        def median(
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
        # NORMAL 1
        # ==================================================

        n1_left = median(
            normal_1,
            "left"
        )

        n1_right = median(
            normal_1,
            "right"
        )


        # ==================================================
        # RAISE LEFT
        # ==================================================

        left_state_left = median(
            raise_left,
            "left"
        )

        left_state_right = median(
            raise_left,
            "right"
        )


        left_delta_left = (
            left_state_left
            -
            n1_left
        )


        left_delta_right = (
            left_state_right
            -
            n1_right
        )


        # Intended shoulder should respond more
        left_response = (
            abs(
                left_delta_left
            )
            >
            abs(
                left_delta_right
            )
        )


        # ==================================================
        # NORMAL 2
        # ==================================================

        n2_left = median(
            normal_2,
            "left"
        )

        n2_right = median(
            normal_2,
            "right"
        )


        return_after_left_left = abs(
            n2_left
            -
            n1_left
        )


        return_after_left_right = abs(
            n2_right
            -
            n1_right
        )


        # ==================================================
        # RAISE RIGHT
        # ==================================================

        right_state_left = median(
            raise_right,
            "left"
        )

        right_state_right = median(
            raise_right,
            "right"
        )


        right_delta_left = (
            right_state_left
            -
            n2_left
        )


        right_delta_right = (
            right_state_right
            -
            n2_right
        )


        right_response = (
            abs(
                right_delta_right
            )
            >
            abs(
                right_delta_left
            )
        )


        # ==================================================
        # NORMAL 3
        # ==================================================

        n3_left = median(
            normal_3,
            "left"
        )

        n3_right = median(
            normal_3,
            "right"
        )


        return_after_right_left = abs(
            n3_left
            -
            n2_left
        )


        return_after_right_right = abs(
            n3_right
            -
            n2_right
        )


        # ==================================================
        # RAISE BOTH
        # ==================================================

        both_state_left = median(
            raise_both,
            "left"
        )

        both_state_right = median(
            raise_both,
            "right"
        )


        both_delta_left = (
            both_state_left
            -
            n3_left
        )


        both_delta_right = (
            both_state_right
            -
            n3_right
        )


        # ==================================================
        # NORMAL 4
        # ==================================================

        n4_left = median(
            normal_4,
            "left"
        )

        n4_right = median(
            normal_4,
            "right"
        )


        return_after_both_left = abs(
            n4_left
            -
            n3_left
        )


        return_after_both_right = abs(
            n4_right
            -
            n3_right
        )


        # ==================================================
        # BOTH Response
        #
        # ต้องการ:
        # - ซ้ายเปลี่ยน
        # - ขวาเปลี่ยน
        # - ไปในทิศทางเดียวกัน
        # - การเปลี่ยนต้องเด่นกว่า normal drift หลังกลับ
        #
        # ไม่มี Risk threshold
        # ==================================================

        both_same_direction = (
            both_delta_left
            *
            both_delta_right
            >
            0
        )


        both_response = (

            both_same_direction

            and

            abs(
                both_delta_left
            )
            >
            return_after_both_left

            and

            abs(
                both_delta_right
            )
            >
            return_after_both_right
        )


        # ==================================================
        # Normal Return
        #
        # ไม่ใช้ threshold ทางคลินิก
        #
        # แค่ตรวจว่า drift ตอนกลับ NORMAL
        # น้อยกว่าการเปลี่ยน deliberate movement
        # ==================================================

        left_return_pass = (
            return_after_left_left
            <
            abs(
                left_delta_left
            )
        )


        right_return_pass = (
            return_after_right_right
            <
            abs(
                right_delta_right
            )
        )


        both_return_pass = (

            return_after_both_left
            <
            abs(
                both_delta_left
            )

            and

            return_after_both_right
            <
            abs(
                both_delta_right
            )
        )


        normal_return_pass = (

            left_return_pass

            and

            right_return_pass

            and

            both_return_pass
        )


        reports.append(
            {

                "round": round_number,

                # ------------------------------------------
                # LEFT
                # ------------------------------------------

                "left_delta_left": (
                    left_delta_left
                ),

                "left_delta_right": (
                    left_delta_right
                ),

                "left_target_sign": (
                    get_sign(
                        left_delta_left
                    )
                ),

                "left_response": (
                    left_response
                ),

                # ------------------------------------------
                # RIGHT
                # ------------------------------------------

                "right_delta_left": (
                    right_delta_left
                ),

                "right_delta_right": (
                    right_delta_right
                ),

                "right_target_sign": (
                    get_sign(
                        right_delta_right
                    )
                ),

                "right_response": (
                    right_response
                ),

                # ------------------------------------------
                # BOTH
                # ------------------------------------------

                "both_delta_left": (
                    both_delta_left
                ),

                "both_delta_right": (
                    both_delta_right
                ),

                "both_left_sign": (
                    get_sign(
                        both_delta_left
                    )
                ),

                "both_right_sign": (
                    get_sign(
                        both_delta_right
                    )
                ),

                "both_same_direction": (
                    both_same_direction
                ),

                "both_response": (
                    both_response
                ),

                # ------------------------------------------
                # Normal Return
                # ------------------------------------------

                "return_after_left_left": (
                    return_after_left_left
                ),

                "return_after_left_right": (
                    return_after_left_right
                ),

                "return_after_right_left": (
                    return_after_right_left
                ),

                "return_after_right_right": (
                    return_after_right_right
                ),

                "return_after_both_left": (
                    return_after_both_left
                ),

                "return_after_both_right": (
                    return_after_both_right
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
        "POSTGUARD SHOULDER ELEVATION VALIDATION REPORT"
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
    #
    # ไม่กำหนด + / - ล่วงหน้า
    # ======================================================

    expected_left_sign = (
        reports[0][
            "left_target_sign"
        ]
    )


    expected_right_sign = (
        reports[0][
            "right_target_sign"
        ]
    )


    expected_both_left_sign = (
        reports[0][
            "both_left_sign"
        ]
    )


    expected_both_right_sign = (
        reports[0][
            "both_right_sign"
        ]
    )


    print(
        "\nObserved Convention"
    )


    print(
        "RAISE_LEFT target:",
        sign_text(
            expected_left_sign
        )
    )


    print(
        "RAISE_RIGHT target:",
        sign_text(
            expected_right_sign
        )
    )


    print(
        "RAISE_BOTH Left:",
        sign_text(
            expected_both_left_sign
        )
    )


    print(
        "RAISE_BOTH Right:",
        sign_text(
            expected_both_right_sign
        )
    )


    # ======================================================
    # Counters
    # ======================================================

    left_response_count = 0

    right_response_count = 0

    both_response_count = 0

    normal_return_count = 0


    # ======================================================
    # Each Round
    # ======================================================

    for report in reports:

        # --------------------------------------------------
        # Direction consistency
        # --------------------------------------------------

        left_direction_consistent = (
            report[
                "left_target_sign"
            ]
            ==
            expected_left_sign
        )


        right_direction_consistent = (
            report[
                "right_target_sign"
            ]
            ==
            expected_right_sign
        )


        both_direction_consistent = (

            report[
                "both_left_sign"
            ]
            ==
            expected_both_left_sign

            and

            report[
                "both_right_sign"
            ]
            ==
            expected_both_right_sign
        )


        # --------------------------------------------------
        # Final response status for this round
        # --------------------------------------------------

        left_pass = (

            report[
                "left_response"
            ]

            and

            left_direction_consistent
        )


        right_pass = (

            report[
                "right_response"
            ]

            and

            right_direction_consistent
        )


        both_pass = (

            report[
                "both_response"
            ]

            and

            both_direction_consistent
        )


        if left_pass:
            left_response_count += 1


        if right_pass:
            right_response_count += 1


        if both_pass:
            both_response_count += 1


        if report[
            "normal_return_pass"
        ]:

            normal_return_count += 1


        # ==================================================
        # Print Round
        # ==================================================

        print(
            f"\nROUND {report['round']}"
        )


        print(
            "----------------------------------------------"
        )


        # ==================================================
        # RAISE LEFT
        # ==================================================

        print(
            "RAISE_LEFT"
        )


        print(
            "  Left Delta :",
            f"{report['left_delta_left']:+.4f}"
        )


        print(
            "  Right Delta:",
            f"{report['left_delta_right']:+.4f}"
        )


        print(
            "  Left Response:",
            (
                "PASS"
                if left_pass
                else "FAIL"
            )
        )


        # ==================================================
        # RAISE RIGHT
        # ==================================================

        print(
            "\nRAISE_RIGHT"
        )


        print(
            "  Left Delta :",
            f"{report['right_delta_left']:+.4f}"
        )


        print(
            "  Right Delta:",
            f"{report['right_delta_right']:+.4f}"
        )


        print(
            "  Right Response:",
            (
                "PASS"
                if right_pass
                else "FAIL"
            )
        )


        # ==================================================
        # RAISE BOTH
        # ==================================================

        print(
            "\nRAISE_BOTH"
        )


        print(
            "  Left Delta :",
            f"{report['both_delta_left']:+.4f}"
        )


        print(
            "  Right Delta:",
            f"{report['both_delta_right']:+.4f}"
        )


        print(
            "  Same Direction:",
            (
                "PASS"
                if report[
                    "both_same_direction"
                ]
                else "FAIL"
            )
        )


        print(
            "  Both Response:",
            (
                "PASS"
                if both_pass
                else "FAIL"
            )
        )


        # ==================================================
        # Normal Return
        # ==================================================

        print(
            "\nNORMAL RETURN"
        )


        print(
            "  After LEFT - Left:",
            f"{report['return_after_left_left']:.4f}"
        )


        print(
            "  After LEFT - Right:",
            f"{report['return_after_left_right']:.4f}"
        )


        print(
            "  After RIGHT - Left:",
            f"{report['return_after_right_left']:.4f}"
        )


        print(
            "  After RIGHT - Right:",
            f"{report['return_after_right_right']:.4f}"
        )


        print(
            "  After BOTH - Left:",
            f"{report['return_after_both_left']:.4f}"
        )


        print(
            "  After BOTH - Right:",
            f"{report['return_after_both_right']:.4f}"
        )


        print(
            "  Normal Return:",
            (
                "PASS"
                if report[
                    "normal_return_pass"
                ]
                else "FAIL"
            )
        )


    # ======================================================
    # Overall Prototype Result
    # ======================================================

    prototype_pass = (

        expected_left_sign
        !=
        0

        and

        expected_right_sign
        !=
        0

        and

        expected_both_left_sign
        !=
        0

        and

        expected_both_right_sign
        !=
        0

        and

        left_response_count
        ==
        3

        and

        right_response_count
        ==
        3

        and

        both_response_count
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
        "LEFT Response Consistency:",
        f"{left_response_count}/3"
    )


    print(
        "RIGHT Response Consistency:",
        f"{right_response_count}/3"
    )


    print(
        "BOTH Response:",
        f"{both_response_count}/3"
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
            "SHOULDER ELEVATION VALIDATION: PASS"
        )


        print(
            "Shoulder Elevation can be LOCKED "
            "as a Validated Prototype Metric."
        )


    else:

        print(
            "SHOULDER ELEVATION VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Shoulder Elevation yet."
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
            "shoulder_elevation_validation_"
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

                "left_median",
                "left_mean",
                "left_std",
                "left_min",
                "left_max",

                "right_median",
                "right_mean",
                "right_std",
                "right_min",
                "right_max",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            left = (
                summary[
                    "left"
                ]
            )


            right = (
                summary[
                    "right"
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

                    left[
                        "median"
                    ],

                    left[
                        "mean"
                    ],

                    left[
                        "std"
                    ],

                    left[
                        "min"
                    ],

                    left[
                        "max"
                    ],

                    right[
                        "median"
                    ],

                    right[
                        "mean"
                    ],

                    right[
                        "std"
                    ],

                    right[
                        "min"
                    ],

                    right[
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
    # Model
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
        # Read RAW frame
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
        # IMPORTANT:
        # Detection / Calculation = RAW frame
        # ==================================================

        pose_points = (
            pose_detector.detect(
                raw_frame
            )
        )


        points_valid = (
            elevation_points_valid(
                pose_points
            )
        )


        shoulder_elevation = None

        left_elevation = None

        right_elevation = None


        # ==================================================
        # Calculate Shoulder Elevation
        # ==================================================

        if points_valid:

            shoulder_elevation = (
                calculate_shoulder_elevation(

                    pose_points[
                        "nose"
                    ],

                    pose_points[
                        "left_shoulder"
                    ],

                    pose_points[
                        "right_shoulder"
                    ],
                )
            )


            if shoulder_elevation is not None:

                if (
                    "left"
                    in
                    shoulder_elevation

                    and

                    "right"
                    in
                    shoulder_elevation

                    and

                    is_finite_number(
                        shoulder_elevation[
                            "left"
                        ]
                    )

                    and

                    is_finite_number(
                        shoulder_elevation[
                            "right"
                        ]
                    )
                ):

                    left_elevation = float(
                        shoulder_elevation[
                            "left"
                        ]
                    )


                    right_elevation = float(
                        shoulder_elevation[
                            "right"
                        ]
                    )


        # ==================================================
        # Metric Validity
        # ==================================================

        metric_valid = (

            left_elevation
            is not None

            and

            right_elevation
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
                        "left": (
                            left_elevation
                        ),

                        "right": (
                            right_elevation
                        ),
                    }
                )


            # ==================================================
            # Capture completed
            # ==================================================

            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ==========================================
                # Not Enough Samples
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
                        "Please retry current state."
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


                    summary = (
                        summarize_samples(
                            samples
                        )
                    )


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
                    # All states completed
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
                                "SHOULDER ELEVATION PASS"
                            )


                        else:

                            status_message = (
                                "SHOULDER ELEVATION NEEDS REVIEW"
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
        # Display Frame
        #
        # Mirror DISPLAY only
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # Draw Metric Visualization
        # ==================================================

        if metric_valid:

            draw_shoulder_elevation_debug(

                frame=(
                    display_frame
                ),

                points=(
                    pose_points
                ),

                left_elevation=(
                    left_elevation
                ),

                right_elevation=(
                    right_elevation
                ),

                mirrored=True,
            )


        else:

            cv2.putText(
                display_frame,
                "Shoulder Elevation: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Current State
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
                "SHOULDER ELEVATION TEST COMPLETE"
            )


            progress_text = (
                "All states completed"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (0, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            progress_text,
            (20, 150),
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
            (20, 185),
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
            "PostGuard - Shoulder Elevation Validation",
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
            key == ord(" ")
            and
            not collecting
            and
            not test_complete
        ):

            if not metric_valid:

                print(
                    "Shoulder Elevation INVALID"
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
        # R = Reset Entire Test
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
                "\nShoulder Elevation Test RESET"
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