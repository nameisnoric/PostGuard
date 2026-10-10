from pathlib import Path
import sys
import time
import csv
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
    calculate_shoulder_tilt
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
# NORMAL
# LEFT HIGH
# NORMAL
# RIGHT HIGH
# NORMAL
#
# x 3 rounds
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
                "state": "LEFT_SHOULDER_HIGH",
            },

            {
                "round": round_number,
                "state": "NORMAL_2",
            },

            {
                "round": round_number,
                "state": "RIGHT_SHOULDER_HIGH",
            },

            {
                "round": round_number,
                "state": "NORMAL_3",
            },
        ]
    )


# ==========================================================
# Validate Shoulder Points
# ==========================================================

def shoulders_valid(points):

    if points is None:
        return False


    required = (
        "left_shoulder",
        "right_shoulder",
    )


    for name in required:

        if name not in points:
            return False


        point = points[name]


        if (
            "x" not in point
            or
            "y" not in point
        ):
            return False


        if (
            point["x"] is None
            or
            point["y"] is None
        ):
            return False


    return True


# ==========================================================
# Mirror coordinate ONLY for display
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
# Shoulder Tilt Debug Drawing
#
# Draws:
#
# - Left Shoulder Point
# - Right Shoulder Point
# - Actual Shoulder Line
# - Horizontal Reference Line
# - L / R Labels
# ==========================================================

def draw_shoulder_tilt_debug(
    frame,
    points,
    shoulder_tilt,
    mirrored=True
):

    if not shoulders_valid(
        points
    ):
        return frame


    frame_height, frame_width = (
        frame.shape[:2]
    )


    left_raw = (
        points[
            "left_shoulder"
        ]
    )


    right_raw = (
        points[
            "right_shoulder"
        ]
    )


    left_point = (
        get_display_point(
            left_raw,
            frame_width,
            mirrored
        )
    )


    right_point = (
        get_display_point(
            right_raw,
            frame_width,
            mirrored
        )
    )


    left_x, left_y = (
        left_point
    )


    right_x, right_y = (
        right_point
    )


    # ======================================================
    # Midpoint
    # ======================================================

    center_x = int(
        (
            left_x
            +
            right_x
        )
        /
        2
    )


    center_y = int(
        (
            left_y
            +
            right_y
        )
        /
        2
    )


    # ======================================================
    # Actual Shoulder Line
    # ======================================================

    cv2.line(
        frame,
        left_point,
        right_point,
        (0, 255, 255),
        3
    )


    # ======================================================
    # Horizontal Reference
    #
    # Length based on shoulder span
    # ======================================================

    shoulder_span = abs(
        right_x
        -
        left_x
    )


    reference_half_length = max(
        int(
            shoulder_span
            *
            0.65
        ),
        80
    )


    reference_start = (
        center_x
        -
        reference_half_length,
        center_y
    )


    reference_end = (
        center_x
        +
        reference_half_length,
        center_y
    )


    cv2.line(
        frame,
        reference_start,
        reference_end,
        (255, 255, 255),
        1
    )


    # ======================================================
    # Shoulder Points
    # ======================================================

    cv2.circle(
        frame,
        left_point,
        8,
        (0, 255, 0),
        -1
    )


    cv2.circle(
        frame,
        right_point,
        8,
        (0, 255, 0),
        -1
    )


    # ======================================================
    # Anatomical Labels
    # ======================================================

    cv2.putText(
        frame,
        "L",
        (
            left_x - 10,
            left_y - 15
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
            right_x - 10,
            right_y - 15
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.60,
        (0, 255, 0),
        2
    )


    # ======================================================
    # Center Point
    # ======================================================

    cv2.circle(
        frame,
        (
            center_x,
            center_y
        ),
        5,
        (255, 255, 255),
        -1
    )


    # ======================================================
    # Tilt Value
    # ======================================================

    cv2.putText(
        frame,
        (
            "Shoulder Tilt: "
            f"{shoulder_tilt:+.2f} deg"
        ),
        (
            20,
            40
        ),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.70,
        (0, 255, 255),
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


# ==========================================================
# Find State
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
    sign
):

    if sign > 0:
        return "POSITIVE (+)"

    if sign < 0:
        return "NEGATIVE (-)"

    return "ZERO"


# ==========================================================
# Print Each Capture
# ==========================================================

def print_state_result(
    step,
    summary
):

    print(
        "\n"
        "========================================"
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
        "----------------------------------------"
    )


    print(
        "Shoulder Tilt"
    )


    print(
        "  Median:",
        f"{summary['tilt']['median']:+.3f} deg"
    )


    print(
        "  Mean  :",
        f"{summary['tilt']['mean']:+.3f} deg"
    )


    print(
        "  Std   :",
        f"{summary['tilt']['std']:.3f} deg"
    )


    print(
        "========================================"
    )


# ==========================================================
# Analyse Round
# ==========================================================

def analyse_rounds(
    results
):

    reports = []


    for round_number in range(
        1,
        4
    ):

        normal_1 = (
            get_state_result(
                results,
                round_number,
                "NORMAL_1"
            )
        )


        left_high = (
            get_state_result(
                results,
                round_number,
                "LEFT_SHOULDER_HIGH"
            )
        )


        normal_2 = (
            get_state_result(
                results,
                round_number,
                "NORMAL_2"
            )
        )


        right_high = (
            get_state_result(
                results,
                round_number,
                "RIGHT_SHOULDER_HIGH"
            )
        )


        normal_3 = (
            get_state_result(
                results,
                round_number,
                "NORMAL_3"
            )
        )


        if any(
            result is None
            for result in (
                normal_1,
                left_high,
                normal_2,
                right_high,
                normal_3,
            )
        ):

            continue


        n1 = (
            normal_1[
                "summary"
            ][
                "tilt"
            ][
                "median"
            ]
        )


        left = (
            left_high[
                "summary"
            ][
                "tilt"
            ][
                "median"
            ]
        )


        n2 = (
            normal_2[
                "summary"
            ][
                "tilt"
            ][
                "median"
            ]
        )


        right = (
            right_high[
                "summary"
            ][
                "tilt"
            ][
                "median"
            ]
        )


        n3 = (
            normal_3[
                "summary"
            ][
                "tilt"
            ][
                "median"
            ]
        )


        # ==================================================
        # Use preceding NORMAL as reference
        # ==================================================

        left_delta = (
            left
            -
            n1
        )


        right_delta = (
            right
            -
            n2
        )


        # ==================================================
        # Return Error
        #
        # After LEFT:
        # NORMAL_2 should return close to NORMAL_1
        #
        # After RIGHT:
        # NORMAL_3 should remain close to NORMAL
        # ==================================================

        return_after_left = abs(
            n2
            -
            n1
        )


        return_after_right = abs(
            n3
            -
            n2
        )


        # ==================================================
        # Opposite Direction
        # ==================================================

        opposite_direction = (
            left_delta
            *
            right_delta
            <
            0
        )


        # ==================================================
        # Normal Return
        #
        # No clinical threshold here.
        #
        # We only require normal drift to be smaller
        # than deliberate shoulder-tilt movement.
        # ==================================================

        smallest_deliberate_change = min(
            abs(
                left_delta
            ),
            abs(
                right_delta
            )
        )


        normal_return_pass = (

            smallest_deliberate_change
            >
            0

            and

            return_after_left
            <
            smallest_deliberate_change

            and

            return_after_right
            <
            smallest_deliberate_change
        )


        reports.append(
            {

                "round": (
                    round_number
                ),

                "normal_1": (
                    n1
                ),

                "left": (
                    left
                ),

                "normal_2": (
                    n2
                ),

                "right": (
                    right
                ),

                "normal_3": (
                    n3
                ),

                "left_delta": (
                    left_delta
                ),

                "right_delta": (
                    right_delta
                ),

                "left_sign": (
                    get_sign(
                        left_delta
                    )
                ),

                "right_sign": (
                    get_sign(
                        right_delta
                    )
                ),

                "return_after_left": (
                    return_after_left
                ),

                "return_after_right": (
                    return_after_right
                ),

                "opposite_direction": (
                    opposite_direction
                ),

                "normal_return_pass": (
                    normal_return_pass
                ),
            }
        )


    return reports


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(
    results
):

    reports = (
        analyse_rounds(
            results
        )
    )


    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD SHOULDER TILT VALIDATION REPORT"
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

    expected_left_sign = (
        reports[0][
            "left_sign"
        ]
    )


    expected_right_sign = (
        reports[0][
            "right_sign"
        ]
    )


    print(
        "\nObserved Convention"
    )


    print(
        "LEFT SHOULDER HIGH :",
        sign_text(
            expected_left_sign
        )
    )


    print(
        "RIGHT SHOULDER HIGH:",
        sign_text(
            expected_right_sign
        )
    )


    opposite_count = 0

    left_consistency = 0

    right_consistency = 0

    normal_return_count = 0


    for report in reports:

        left_consistent = (
            report[
                "left_sign"
            ]
            ==
            expected_left_sign
        )


        right_consistent = (
            report[
                "right_sign"
            ]
            ==
            expected_right_sign
        )


        if report[
            "opposite_direction"
        ]:

            opposite_count += 1


        if left_consistent:

            left_consistency += 1


        if right_consistent:

            right_consistency += 1


        if report[
            "normal_return_pass"
        ]:

            normal_return_count += 1


        print(
            f"\nROUND {report['round']}"
        )


        print(
            "----------------------------------------"
        )


        print(
            "NORMAL_1:",
            f"{report['normal_1']:+.3f} deg"
        )


        print(
            "LEFT HIGH:",
            f"{report['left']:+.3f} deg"
        )


        print(
            "LEFT Delta:",
            f"{report['left_delta']:+.3f} deg"
        )


        print(
            "NORMAL_2:",
            f"{report['normal_2']:+.3f} deg"
        )


        print(
            "Return Error after LEFT:",
            f"{report['return_after_left']:.3f} deg"
        )


        print(
            "RIGHT HIGH:",
            f"{report['right']:+.3f} deg"
        )


        print(
            "RIGHT Delta:",
            f"{report['right_delta']:+.3f} deg"
        )


        print(
            "NORMAL_3:",
            f"{report['normal_3']:+.3f} deg"
        )


        print(
            "Return Error after RIGHT:",
            f"{report['return_after_right']:.3f} deg"
        )


        print(
            "Opposite Direction:",
            (
                "PASS"
                if report[
                    "opposite_direction"
                ]
                else "FAIL"
            )
        )


        print(
            "LEFT Consistency:",
            (
                "PASS"
                if left_consistent
                else "FAIL"
            )
        )


        print(
            "RIGHT Consistency:",
            (
                "PASS"
                if right_consistent
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
    # Overall Result
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

        expected_left_sign
        !=
        expected_right_sign

        and

        opposite_count
        ==
        3

        and

        left_consistency
        ==
        3

        and

        right_consistency
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
        "Opposite Direction:",
        f"{opposite_count}/3"
    )


    print(
        "LEFT Direction Consistency:",
        f"{left_consistency}/3"
    )


    print(
        "RIGHT Direction Consistency:",
        f"{right_consistency}/3"
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
            "SHOULDER TILT VALIDATION: PASS"
        )


        print(
            "Shoulder Tilt can be LOCKED as a "
            "Validated Prototype Metric."
        )


    else:

        print(
            "SHOULDER TILT VALIDATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Shoulder Tilt yet."
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
            "shoulder_tilt_validation_"
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

        writer = (
            csv.writer(
                file
            )
        )


        writer.writerow(
            [
                "round",
                "state",
                "samples",
                "tilt_median",
                "tilt_mean",
                "tilt_std",
                "tilt_min",
                "tilt_max",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            tilt = (
                summary[
                    "tilt"
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

                    tilt[
                        "median"
                    ],

                    tilt[
                        "mean"
                    ],

                    tilt[
                        "std"
                    ],

                    tilt[
                        "min"
                    ],

                    tilt[
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


    pose_detector = (
        PoseDetector(
            POSE_MODEL_PATH
        )
    )


    # ======================================================
    # Camera
    # ======================================================

    cap = (
        cv2.VideoCapture(
            0
        )
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
    # Runtime
    # ======================================================

    test_index = 0

    results = []


    collecting = False

    collection_start = None

    samples = []


    test_complete = False

    saved = False


    status_message = (
        "Press SPACE to capture"
    )


    while True:

        ret, raw_frame = (
            cap.read()
        )


        if not ret:
            break


        frame_height, frame_width = (
            raw_frame.shape[:2]
        )


        # ==================================================
        # Detect from RAW FRAME
        # ==================================================

        pose_points = (
            pose_detector.detect(
                raw_frame
            )
        )


        valid = (
            shoulders_valid(
                pose_points
            )
        )


        shoulder_tilt = None


        if valid:

            shoulder_tilt = (
                calculate_shoulder_tilt(
                    pose_points[
                        "left_shoulder"
                    ],
                    pose_points[
                        "right_shoulder"
                    ]
                )
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


            if (
                valid
                and
                shoulder_tilt is not None
            ):

                samples.append(
                    shoulder_tilt
                )


            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


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


                    status_message = (
                        "RETRY CURRENT STATE"
                    )


                    samples = []


                else:

                    step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    tilt_summary = (
                        summarize_values(
                            samples
                        )
                    )


                    summary = {

                        "samples": (
                            len(
                                samples
                            )
                        ),

                        "tilt": (
                            tilt_summary
                        ),
                    }


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

                        "summary": (
                            summary
                        ),
                    }


                    results.append(
                        record
                    )


                    print_state_result(
                        step,
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


                        if not saved:

                            save_results(
                                results
                            )

                            saved = True


                        if final_pass:

                            status_message = (
                                "SHOULDER TILT PASS"
                            )


                        else:

                            status_message = (
                                "SHOULDER TILT NEEDS REVIEW"
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

        display_frame = (
            cv2.flip(
                raw_frame,
                1
            )
        )


        # ==================================================
        # Draw Shoulder Tilt
        # ==================================================

        if (
            valid
            and
            shoulder_tilt is not None
        ):

            draw_shoulder_tilt_debug(

                frame=(
                    display_frame
                ),

                points=(
                    pose_points
                ),

                shoulder_tilt=(
                    shoulder_tilt
                ),

                mirrored=True,
            )


        else:

            cv2.putText(
                display_frame,
                "Shoulders: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
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


        else:

            state_text = (
                "SHOULDER TILT TEST COMPLETE"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (255, 255, 255),
            2
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
                f"CAPTURING "
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
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            2
        )


        # ==================================================
        # Instructions
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


        cv2.imshow(
            "PostGuard - Shoulder Tilt Validation",
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
        # Capture
        # ==================================================

        if (
            key == ord(" ")
            and
            not collecting
            and
            not test_complete
        ):

            if (
                not valid
                or
                shoulder_tilt is None
            ):

                print(
                    "Shoulders INVALID"
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
        # Reset
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

            saved = False


            status_message = (
                "RESET - Round 1 NORMAL_1"
            )


            print(
                "\nShoulder Tilt Test RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()

    pose_detector.close()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    main()