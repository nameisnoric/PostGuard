from pathlib import Path
import sys
import time
import math
import csv
from datetime import datetime

import cv2
import numpy as np


# ==========================================================
# Project Root
# ==========================================================

DESKTOP_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(DESKTOP_DIR)
    )


# ==========================================================
# PostGuard Modules
# ==========================================================

from app.vision.mediapipe_detection.face.face_detector import (
    FaceDetector
)

from app.vision.mediapipe_detection.face.face_points import (
    extract_face_points
)

from app.vision.mediapipe_detection.face.face_orientation import (
    extract_face_orientation
)

from app.vision.mediapipe_detection.posture.relative_distance import (
    calculate_eye_distance
)


# ==========================================================
# Model Path
# ==========================================================

FACE_MODEL_PATH = (
    DESKTOP_DIR
    / "app"
    / "vision"
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Test Settings
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0
MIN_VALID_SAMPLES = 15
TOTAL_ROUNDS = 3


# ==========================================================
# Test Sequence
#
# เป้าหมาย:
#
# NORMAL
#     ↓
# HEAD_LEFT
#     ↓
# NORMAL
#     ↓
# HEAD_RIGHT
#     ↓
# NORMAL
#     ↓
# MOVE_CLOSER
#     ↓
# NORMAL
#
# MOVE_CLOSER = Positive Control
#
# เราไม่ได้กำหนด threshold ทางการแพทย์
# test นี้ดูว่า rotation cross-talk
# มีขนาดเล็กกว่า movement signal จริงหรือไม่
# ==========================================================

TEST_SEQUENCE = []

for round_number in range(
    1,
    TOTAL_ROUNDS + 1
):
    TEST_SEQUENCE.extend(
        [
            {
                "round": round_number,
                "state": "NORMAL_1",
            },
            {
                "round": round_number,
                "state": "HEAD_LEFT",
            },
            {
                "round": round_number,
                "state": "NORMAL_2",
            },
            {
                "round": round_number,
                "state": "HEAD_RIGHT",
            },
            {
                "round": round_number,
                "state": "NORMAL_3",
            },
            {
                "round": round_number,
                "state": "MOVE_CLOSER",
            },
            {
                "round": round_number,
                "state": "NORMAL_4",
            },
        ]
    )


# ==========================================================
# Numeric Helpers
# ==========================================================

def is_finite_number(value):

    try:
        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return False


def summarize(values):

    array = np.asarray(
        values,
        dtype=np.float64,
    )

    return {
        "median": float(
            np.median(array)
        ),
        "mean": float(
            np.mean(array)
        ),
        "std": float(
            np.std(array)
        ),
        "min": float(
            np.min(array)
        ),
        "max": float(
            np.max(array)
        ),
    }


# ==========================================================
# Find State
# ==========================================================

def get_result(
    results,
    round_number,
    state,
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
# Capture Summary
# ==========================================================

def summarize_samples(samples):

    eye_values = [
        sample["eye_distance"]
        for sample in samples
    ]

    yaw_values = [
        sample["yaw"]
        for sample in samples
        if is_finite_number(
            sample.get("yaw")
        )
    ]

    result = {
        "samples": len(samples),
        "eye_distance": summarize(
            eye_values
        ),
        "yaw": None,
    }

    if yaw_values:
        result["yaw"] = summarize(
            yaw_values
        )

    return result


# ==========================================================
# Print State
# ==========================================================

def print_state_result(
    step,
    summary,
):

    print()
    print(
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
        "Inter-Eye Distance"
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

    if summary["yaw"] is not None:

        print(
            "Face Yaw"
        )
        print(
            "  Median:",
            f"{summary['yaw']['median']:+.3f} deg"
        )
        print(
            "  Std   :",
            f"{summary['yaw']['std']:.3f} deg"
        )

    print(
        "=============================================="
    )


# ==========================================================
# Analyse One Round
# ==========================================================

def analyse_round(
    results,
    round_number,
):

    normal_1 = get_result(
        results,
        round_number,
        "NORMAL_1",
    )

    head_left = get_result(
        results,
        round_number,
        "HEAD_LEFT",
    )

    normal_2 = get_result(
        results,
        round_number,
        "NORMAL_2",
    )

    head_right = get_result(
        results,
        round_number,
        "HEAD_RIGHT",
    )

    normal_3 = get_result(
        results,
        round_number,
        "NORMAL_3",
    )

    move_closer = get_result(
        results,
        round_number,
        "MOVE_CLOSER",
    )

    normal_4 = get_result(
        results,
        round_number,
        "NORMAL_4",
    )

    required = (
        normal_1,
        head_left,
        normal_2,
        head_right,
        normal_3,
        move_closer,
        normal_4,
    )

    if any(
        item is None
        for item in required
    ):
        return None

    n1 = (
        normal_1["summary"]
        ["eye_distance"]
        ["median"]
    )

    left = (
        head_left["summary"]
        ["eye_distance"]
        ["median"]
    )

    n2 = (
        normal_2["summary"]
        ["eye_distance"]
        ["median"]
    )

    right = (
        head_right["summary"]
        ["eye_distance"]
        ["median"]
    )

    n3 = (
        normal_3["summary"]
        ["eye_distance"]
        ["median"]
    )

    closer = (
        move_closer["summary"]
        ["eye_distance"]
        ["median"]
    )

    n4 = (
        normal_4["summary"]
        ["eye_distance"]
        ["median"]
    )


    # ======================================================
    # Local Baselines
    #
    # ใช้ normal ที่อยู่ก่อน state นั้นโดยตรง
    # เพื่อลดผลจาก drift ระหว่างการทดลอง
    # ======================================================

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

    closer_delta = (
        closer
        -
        n3
    )


    # ======================================================
    # Absolute Cross-talk
    # ======================================================

    left_abs = abs(
        left_delta
    )

    right_abs = abs(
        right_delta
    )

    closer_abs = abs(
        closer_delta
    )


    # ======================================================
    # Cross-talk Ratio
    #
    # rotation change / real closer change
    #
    # ยิ่งต่ำยิ่งดี
    #
    # IMPORTANT:
    # ยังไม่ใช้ hard threshold เช่น 0.2 / 0.3
    # เพราะต้องดูข้อมูลจริงก่อน
    # ======================================================

    left_crosstalk_ratio = (
        left_abs / closer_abs
        if closer_abs > 1e-6
        else None
    )

    right_crosstalk_ratio = (
        right_abs / closer_abs
        if closer_abs > 1e-6
        else None
    )


    # ======================================================
    # Positive Control
    #
    # MOVE_CLOSER ต้องทำให้ eye distance เพิ่ม
    # ======================================================

    closer_direction_pass = (
        closer_delta > 0.0
    )


    # ======================================================
    # Comparative Check
    #
    # ยังไม่ใช่ production threshold
    #
    # แค่ตรวจว่า deliberate closer movement
    # มี signal ใหญ่กว่า rotation
    # ======================================================

    left_separated = (
        closer_abs
        >
        left_abs
    )

    right_separated = (
        closer_abs
        >
        right_abs
    )


    # ======================================================
    # Return Errors
    # ======================================================

    return_after_left = abs(
        n2 - n1
    )

    return_after_right = abs(
        n3 - n2
    )

    return_after_closer = abs(
        n4 - n3
    )


    return {
        "round": round_number,

        "normal_1": n1,
        "head_left": left,
        "normal_2": n2,
        "head_right": right,
        "normal_3": n3,
        "move_closer": closer,
        "normal_4": n4,

        "left_delta": left_delta,
        "right_delta": right_delta,
        "closer_delta": closer_delta,

        "left_abs": left_abs,
        "right_abs": right_abs,
        "closer_abs": closer_abs,

        "left_crosstalk_ratio":
            left_crosstalk_ratio,

        "right_crosstalk_ratio":
            right_crosstalk_ratio,

        "closer_direction_pass":
            closer_direction_pass,

        "left_separated":
            left_separated,

        "right_separated":
            right_separated,

        "return_after_left":
            return_after_left,

        "return_after_right":
            return_after_right,

        "return_after_closer":
            return_after_closer,
    }


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(results):

    print()
    print()
    print(
        "################################################"
    )
    print(
        "POSTGUARD RELATIVE DISTANCE"
    )
    print(
        "ROTATION CROSS-TALK VALIDATION REPORT"
    )
    print(
        "################################################"
    )

    reports = []

    for round_number in range(
        1,
        TOTAL_ROUNDS + 1
    ):

        report = analyse_round(
            results,
            round_number,
        )

        if report is None:
            continue

        reports.append(
            report
        )

        print()
        print(
            f"ROUND {round_number}"
        )
        print(
            "----------------------------------------------"
        )

        print(
            "HEAD_LEFT"
        )
        print(
            "  Delta:",
            f"{report['left_delta']:+.3f} px"
        )
        print(
            "  Cross-talk ratio:",
            f"{report['left_crosstalk_ratio']:.3f}"
        )
        print(
            "  Separated from CLOSER:",
            (
                "PASS"
                if report["left_separated"]
                else "FAIL"
            )
        )

        print()

        print(
            "HEAD_RIGHT"
        )
        print(
            "  Delta:",
            f"{report['right_delta']:+.3f} px"
        )
        print(
            "  Cross-talk ratio:",
            f"{report['right_crosstalk_ratio']:.3f}"
        )
        print(
            "  Separated from CLOSER:",
            (
                "PASS"
                if report["right_separated"]
                else "FAIL"
            )
        )

        print()

        print(
            "MOVE_CLOSER"
        )
        print(
            "  Delta:",
            f"{report['closer_delta']:+.3f} px"
        )
        print(
            "  Direction:",
            (
                "PASS"
                if report[
                    "closer_direction_pass"
                ]
                else "FAIL"
            )
        )

        print()

        print(
            "NORMAL RETURN ERRORS"
        )
        print(
            "  After LEFT :",
            f"{report['return_after_left']:.3f} px"
        )
        print(
            "  After RIGHT:",
            f"{report['return_after_right']:.3f} px"
        )
        print(
            "  After CLOSE:",
            f"{report['return_after_closer']:.3f} px"
        )


    if not reports:

        print(
            "\nERROR: No complete rounds."
        )
        return


    left_passes = sum(
        report["left_separated"]
        for report in reports
    )

    right_passes = sum(
        report["right_separated"]
        for report in reports
    )

    closer_passes = sum(
        report["closer_direction_pass"]
        for report in reports
    )


    left_ratios = [
        report["left_crosstalk_ratio"]
        for report in reports
        if report["left_crosstalk_ratio"]
        is not None
    ]

    right_ratios = [
        report["right_crosstalk_ratio"]
        for report in reports
        if report["right_crosstalk_ratio"]
        is not None
    ]


    print()
    print(
        "================================================"
    )

    print(
        "LEFT separation:",
        f"{left_passes}/{len(reports)}"
    )

    print(
        "RIGHT separation:",
        f"{right_passes}/{len(reports)}"
    )

    print(
        "CLOSER positive control:",
        f"{closer_passes}/{len(reports)}"
    )


    if left_ratios:

        print(
            "Median LEFT cross-talk ratio:",
            f"{np.median(left_ratios):.3f}"
        )


    if right_ratios:

        print(
            "Median RIGHT cross-talk ratio:",
            f"{np.median(right_ratios):.3f}"
        )


    comparative_pass = (
        left_passes
        ==
        len(reports)

        and

        right_passes
        ==
        len(reports)

        and

        closer_passes
        ==
        len(reports)
    )


    print(
        "------------------------------------------------"
    )

    if comparative_pass:

        print(
            "ROTATION CROSS-TALK COMPARATIVE CHECK: PASS"
        )

        print(
            "Rotation signal is smaller than "
            "the deliberate closer signal in all rounds."
        )

    else:

        print(
            "ROTATION CROSS-TALK COMPARATIVE CHECK: "
            "NEEDS REVIEW"
        )

        print(
            "Do NOT define SCREEN_TOO_CLOSE threshold yet."
        )


    print(
        "================================================"
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "PASS here does NOT define a production threshold."
    )

    print(
        "Cross-talk ratios must be reviewed before "
        "SCREEN_TOO_CLOSE is implemented."
    )


# ==========================================================
# Save CSV
# ==========================================================

def save_results(results):

    output_dir = (
        Path(__file__)
        .resolve()
        .parent
        / "results"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
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
            "relative_distance_rotation_crosstalk_"
            f"{timestamp}.csv"
        )
    )


    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
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
                "yaw_median_deg",
                "yaw_std_deg",
            ]
        )


        for result in results:

            summary = result[
                "summary"
            ]

            yaw = summary[
                "yaw"
            ]

            writer.writerow(
                [
                    result["round"],
                    result["state"],
                    summary["samples"],

                    summary[
                        "eye_distance"
                    ][
                        "median"
                    ],

                    summary[
                        "eye_distance"
                    ][
                        "mean"
                    ],

                    summary[
                        "eye_distance"
                    ][
                        "std"
                    ],

                    (
                        yaw["median"]
                        if yaw
                        else None
                    ),

                    (
                        yaw["std"]
                        if yaw
                        else None
                    ),
                ]
            )


    print(
        "\nCSV saved:"
    )

    print(
        output_path
    )


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "PostGuard Relative Distance "
        "Rotation Cross-talk Validation"
    )

    print(
        "Model:",
        FACE_MODEL_PATH
    )


    face_detector = FaceDetector(
        model_path=str(
            FACE_MODEL_PATH
        )
    )


    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        face_detector.close()

        raise RuntimeError(
            "Cannot open camera."
        )


    test_index = 0

    results = []

    collecting = False

    collection_start = None

    samples = []

    test_complete = False

    results_saved = False


    while True:

        ok, frame = cap.read()


        if not ok:
            continue


        frame_height, frame_width = (
            frame.shape[:2]
        )


        # ==================================================
        # Face Detection
        # ==================================================

        face_result = (
            face_detector.detect(
                frame
            )
        )


        face_points = (
            extract_face_points(
                face_result,
                frame_width,
                frame_height,
            )
        )


        orientation = (
            extract_face_orientation(
                face_result
            )
        )


        eye_result = (
            calculate_eye_distance(
                face_points
            )
        )


        eye_distance = None

        if isinstance(
            eye_result,
            dict,
        ):

            eye_distance = (
                eye_result.get(
                    "eye_distance_px"
                )
            )


        yaw = None

        if isinstance(
            orientation,
            dict,
        ):

            yaw = orientation.get(
                "yaw"
            )


        metric_valid = (
            is_finite_number(
                eye_distance
            )
        )


        # ==================================================
        # Collect
        # ==================================================

        if collecting:

            if metric_valid:

                samples.append(
                    {
                        "eye_distance":
                            float(
                                eye_distance
                            ),

                        "yaw":
                            (
                                float(yaw)
                                if is_finite_number(
                                    yaw
                                )
                                else None
                            ),
                    }
                )


            elapsed = (
                time.perf_counter()
                -
                collection_start
            )


            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                current_step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                if (
                    len(samples)
                    <
                    MIN_VALID_SAMPLES
                ):

                    print(
                        "\nNOT ENOUGH VALID SAMPLES"
                    )

                    print(
                        "Repeat:",
                        current_step
                    )

                    collecting = False

                    collection_start = None

                    samples = []


                else:

                    summary = (
                        summarize_samples(
                            samples
                        )
                    )


                    result = {
                        "round":
                            current_step[
                                "round"
                            ],

                        "state":
                            current_step[
                                "state"
                            ],

                        "summary":
                            summary,
                    }


                    results.append(
                        result
                    )


                    print_state_result(
                        current_step,
                        summary,
                    )


                    test_index += 1

                    collecting = False

                    collection_start = None

                    samples = []


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


                        if not results_saved:

                            save_results(
                                results
                            )

                            results_saved = True


        # ==================================================
        # Display
        # ==================================================

        display = cv2.flip(
            frame,
            1,
        )


        if not test_complete:

            step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )

            instruction = (
                f"Round {step['round']} "
                f"- {step['state']}"
            )

        else:

            instruction = (
                "TEST COMPLETE"
            )


        cv2.putText(
            display,
            instruction,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
        )


        if metric_valid:

            cv2.putText(
                display,
                (
                    "Eye Distance: "
                    f"{eye_distance:.2f} px"
                ),
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2,
            )


        if is_finite_number(
            yaw
        ):

            cv2.putText(
                display,
                (
                    "Face Yaw: "
                    f"{yaw:+.2f} deg"
                ),
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 255, 255),
                2,
            )


        if collecting:

            elapsed = min(
                time.perf_counter()
                -
                collection_start,
                SAMPLE_DURATION_SECONDS,
            )

            status = (
                f"CAPTURING {elapsed:.1f}/"
                f"{SAMPLE_DURATION_SECONDS:.1f}s "
                f"samples={len(samples)}"
            )

        else:

            status = (
                "SPACE=Capture"
            )


        cv2.putText(
            display,
            status,
            (20, 140),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
        )


        cv2.putText(
            display,
            "SPACE=Capture  R=Reset  Q=Quit",
            (
                20,
                frame_height - 25,
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            1,
        )


        cv2.imshow(
            (
                "PostGuard - Relative Distance "
                "Rotation Cross-talk"
            ),
            display,
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
            27,
        ):
            break


        # ==================================================
        # Capture
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
                    "Eye Distance INVALID"
                )

                continue


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
            ord("R"),
        ):

            test_index = 0

            results = []

            collecting = False

            collection_start = None

            samples = []

            test_complete = False

            results_saved = False

            print(
                "\nTEST RESET"
            )


    cap.release()

    face_detector.close()

    cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":
    main()