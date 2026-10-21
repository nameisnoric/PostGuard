import sys
import csv
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


# ==========================================================
# Project Root
# ==========================================================

CAMERA_CARD_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

if str(CAMERA_CARD_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CAMERA_CARD_DIR)
    )


# ==========================================================
# Detection Pipeline
# ==========================================================

from mediapipe_detection.detection_pipeline import (
    DetectionPipeline
)


# ==========================================================
# Camera Settings
# ==========================================================

CAMERA_INDEX = 0

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720

WINDOW_NAME = (
    "PostGuard - Forward Head Final Test"
)


# ==========================================================
# Capture Quality Settings
#
# ไม่ใช่ Risk Threshold
# ไม่ใช่ Medical Threshold
#
# เพียงกำหนดว่าแต่ละ State
# ต้องมีข้อมูลเพียงพอสำหรับสรุปค่า
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# Main Forward Head Test
#
# 3 Rounds:
#
# NORMAL_1
# FORWARD_HEAD
# NORMAL_2
#
# ==========================================================

MAIN_TEST_SEQUENCE = []

for round_number in range(1, 4):

    MAIN_TEST_SEQUENCE.extend(
        [
            {
                "type": "MAIN",
                "round": round_number,
                "state": "NORMAL_1",
            },

            {
                "type": "MAIN",
                "round": round_number,
                "state": "FORWARD_HEAD",
            },

            {
                "type": "MAIN",
                "round": round_number,
                "state": "NORMAL_2",
            },
        ]
    )


# ==========================================================
# Distractor Test
#
# ใช้ตรวจว่า Forward Head Metric
# ถูกกระตุ้นจากท่าที่ไม่ใช่ Forward Head
# มากเกินไปหรือไม่
#
# FLEXION:
# ก้มคอ โดยไม่ยื่นศีรษะ
#
# TORSO_LEAN:
# โน้มลำตัวจากสะโพก/ลำตัวไปข้างหน้า
# โดยพยายามรักษาคอเป็นกลาง
# ==========================================================

DISTRACTOR_SEQUENCE = [
    {
        "type": "DISTRACTOR",
        "round": 0,
        "state": "FLEXION_NORMAL",
    },

    {
        "type": "DISTRACTOR",
        "round": 0,
        "state": "FLEXION_DISTRACTOR",
    },

    {
        "type": "DISTRACTOR",
        "round": 0,
        "state": "TORSO_NORMAL",
    },

    {
        "type": "DISTRACTOR",
        "round": 0,
        "state": "TORSO_LEAN_DISTRACTOR",
    },
]


# ==========================================================
# Complete Test Sequence
# ==========================================================

TEST_SEQUENCE = (
    MAIN_TEST_SEQUENCE
    +
    DISTRACTOR_SEQUENCE
)


# ==========================================================
# Colors
# OpenCV = BGR
# ==========================================================

WHITE = (255, 255, 255)

GREEN = (0, 255, 0)

YELLOW = (0, 255, 255)

RED = (0, 0, 255)

CYAN = (255, 255, 0)


# ==========================================================
# Draw Text
# ==========================================================

def put(
    frame,
    text,
    y,
    color=WHITE,
    x=20,
    scale=0.6,
    thickness=1,
):

    cv2.putText(
        frame,
        str(text),
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


# ==========================================================
# Numerical Summary
# ==========================================================

def summarize_values(values):

    values = np.asarray(
        values,
        dtype=np.float64
    )

    return {
        "median": float(
            np.median(values)
        ),

        "mean": float(
            np.mean(values)
        ),

        "std": float(
            np.std(values)
        ),

        "min": float(
            np.min(values)
        ),

        "max": float(
            np.max(values)
        ),
    }


# ==========================================================
# Summarize Samples
# ==========================================================

def summarize_samples(samples):

    forward_values = [
        sample["forward_head"]
        for sample in samples
    ]

    pitch_values = [
        sample["pitch"]
        for sample in samples
    ]

    eye_distance_values = [
        sample["eye_distance"]
        for sample in samples
        if sample["eye_distance"] is not None
    ]

    nose_z_values = [
        sample["nose_z"]
        for sample in samples
        if sample["nose_z"] is not None
    ]

    shoulder_mid_z_values = [
        sample["shoulder_mid_z"]
        for sample in samples
        if sample["shoulder_mid_z"] is not None
    ]


    result = {
        "samples": len(samples),

        "forward_head": summarize_values(
            forward_values
        ),

        "pitch": summarize_values(
            pitch_values
        ),
    }


    if eye_distance_values:

        result["eye_distance"] = (
            summarize_values(
                eye_distance_values
            )
        )

    else:

        result["eye_distance"] = None


    if nose_z_values:

        result["nose_z"] = (
            summarize_values(
                nose_z_values
            )
        )

    else:

        result["nose_z"] = None


    if shoulder_mid_z_values:

        result["shoulder_mid_z"] = (
            summarize_values(
                shoulder_mid_z_values
            )
        )

    else:

        result["shoulder_mid_z"] = None


    return result


# ==========================================================
# Find Main State
# ==========================================================

def get_main_state(
    results,
    round_number,
    state,
):

    for item in results:

        if (
            item["type"] == "MAIN"
            and
            item["round"] == round_number
            and
            item["state"] == state
        ):

            return item

    return None


# ==========================================================
# Find Distractor State
# ==========================================================

def get_distractor_state(
    results,
    state,
):

    for item in results:

        if (
            item["type"] == "DISTRACTOR"
            and
            item["state"] == state
        ):

            return item

    return None


# ==========================================================
# Analyse Main Forward Head Test
# ==========================================================

def analyse_main_test(results):
    """
    วิเคราะห์ Forward Head ทั้ง 3 รอบ

    ไม่มี Threshold แบบ:
        ต้องเปลี่ยน > 0.1
        ต้องเปลี่ยน > 10 องศา

    เราดู:
    - Direction
    - Separation จาก Normal
    - Consistency 3 รอบ
    - Within-state variability
    """

    reports = []


    for round_number in range(
        1,
        4
    ):

        normal_1 = get_main_state(
            results,
            round_number,
            "NORMAL_1"
        )

        forward = get_main_state(
            results,
            round_number,
            "FORWARD_HEAD"
        )

        normal_2 = get_main_state(
            results,
            round_number,
            "NORMAL_2"
        )


        if (
            normal_1 is None
            or
            forward is None
            or
            normal_2 is None
        ):

            continue


        n1 = (
            normal_1["summary"]
            ["forward_head"]
            ["median"]
        )

        n2 = (
            normal_2["summary"]
            ["forward_head"]
            ["median"]
        )

        fwd = (
            forward["summary"]
            ["forward_head"]
            ["median"]
        )


        # ==================================================
        # Neutral Reference
        # ==========================================================

        normal_reference = float(
            np.median(
                [
                    n1,
                    n2,
                ]
            )
        )


        # ==================================================
        # Forward Delta
        # ==========================================================

        forward_delta = (
            fwd
            -
            normal_reference
        )


        # ==================================================
        # Normal Return Error
        #
        # Diagnostic เท่านั้น
        # ==========================================================

        normal_return_error = abs(
            n2
            -
            n1
        )


        # ==================================================
        # Normal Range
        # ==========================================================

        normal_min = min(
            n1,
            n2
        )

        normal_max = max(
            n1,
            n2
        )


        # ==================================================
        # Forward Head Separation Direction
        #
        # ยังไม่สมมติว่า Positive หรือ Negative
        #
        # ถ้าอยู่เหนือ Neutral ทั้งสอง
        # -> POSITIVE
        #
        # ถ้าต่ำกว่า Neutral ทั้งสอง
        # -> NEGATIVE
        #
        # ถ้าอยู่คั่นกลาง
        # -> NOT SEPARATED
        # ==========================================================

        if fwd > normal_max:

            direction = 1

            separated = True

        elif fwd < normal_min:

            direction = -1

            separated = True

        else:

            direction = 0

            separated = False


        # ==================================================
        # Pitch Diagnostic
        #
        # Forward Head ไม่ควรต้องอาศัย
        # Neck Pitch เป็นตัวหลัก
        #
        # รายงานไว้ก่อน
        # ไม่ใช้ Hard Threshold
        # ==========================================================

        normal_pitch = float(
            np.median(
                [
                    normal_1["summary"]
                    ["pitch"]
                    ["median"],

                    normal_2["summary"]
                    ["pitch"]
                    ["median"],
                ]
            )
        )

        forward_pitch = (
            forward["summary"]
            ["pitch"]
            ["median"]
        )

        pitch_delta = (
            forward_pitch
            -
            normal_pitch
        )


        # ==================================================
        # Within-state SD
        # ==========================================================

        n1_std = (
            normal_1["summary"]
            ["forward_head"]
            ["std"]
        )

        n2_std = (
            normal_2["summary"]
            ["forward_head"]
            ["std"]
        )

        forward_std = (
            forward["summary"]
            ["forward_head"]
            ["std"]
        )


        reports.append(
            {
                "round": round_number,

                "normal_1": n1,

                "normal_2": n2,

                "normal_reference": (
                    normal_reference
                ),

                "forward": fwd,

                "forward_delta": (
                    forward_delta
                ),

                "normal_return_error": (
                    normal_return_error
                ),

                "direction": direction,

                "separated": separated,

                "pitch_delta": (
                    pitch_delta
                ),

                "normal_1_std": (
                    n1_std
                ),

                "normal_2_std": (
                    n2_std
                ),

                "forward_std": (
                    forward_std
                ),
            }
        )


    return reports


# ==========================================================
# Determine Direction Convention
# ==========================================================

def determine_forward_direction(
    reports
):
    """
    ดู Direction ทั้ง 3 รอบ

    ถ้าทั้งหมด +:
        Positive Convention

    ถ้าทั้งหมด -:
        Negative Convention

    ถ้าปนกัน:
        Inconsistent
    """

    if len(reports) != 3:

        return 0


    directions = [
        report["direction"]
        for report in reports
    ]


    if all(
        direction == 1
        for direction in directions
    ):

        return 1


    if all(
        direction == -1
        for direction in directions
    ):

        return -1


    return 0


# ==========================================================
# Analyse Distractors
# ==========================================================

def analyse_distractors(
    results,
    forward_direction,
    main_reports,
):
    """
    ดูว่า:

    Flexion อย่างเดียว
    หรือ
    Torso Lean อย่างเดียว

    ทำให้ Forward Head Metric
    เลียนแบบ Forward Head จริงมากแค่ไหน


    ไม่มี Absolute Threshold

    เราเปรียบเทียบกับ
    Response ของ Forward Head จริงโดยตรง
    """

    flex_normal = get_distractor_state(
        results,
        "FLEXION_NORMAL"
    )

    flexion = get_distractor_state(
        results,
        "FLEXION_DISTRACTOR"
    )

    torso_normal = get_distractor_state(
        results,
        "TORSO_NORMAL"
    )

    torso_lean = get_distractor_state(
        results,
        "TORSO_LEAN_DISTRACTOR"
    )


    if (
        flex_normal is None
        or
        flexion is None
        or
        torso_normal is None
        or
        torso_lean is None
    ):

        return None


    # ======================================================
    # Main Forward Response
    # ==========================================================

    main_responses = [
        abs(
            report[
                "forward_delta"
            ]
        )
        for report in main_reports
    ]


    main_response_median = float(
        np.median(
            main_responses
        )
    )


    # ======================================================
    # Flexion Distractor
    # ==========================================================

    flex_normal_value = (
        flex_normal["summary"]
        ["forward_head"]
        ["median"]
    )

    flex_value = (
        flexion["summary"]
        ["forward_head"]
        ["median"]
    )

    flex_delta = (
        flex_value
        -
        flex_normal_value
    )


    # ======================================================
    # Torso Lean Distractor
    # ==========================================================

    torso_normal_value = (
        torso_normal["summary"]
        ["forward_head"]
        ["median"]
    )

    torso_value = (
        torso_lean["summary"]
        ["forward_head"]
        ["median"]
    )

    torso_delta = (
        torso_value
        -
        torso_normal_value
    )


    # ======================================================
    # Mimic Response
    #
    # คำนวณเฉพาะ component
    # ที่ไปในทิศเดียวกับ Forward Head จริง
    #
    # ถ้าค่าเป็นลบ
    # แปลว่า Distractor ไปคนละทิศ
    # จึงไม่ถือว่า Mimic
    # ==========================================================

    flex_mimic = (
        forward_direction
        *
        flex_delta
    )

    torso_mimic = (
        forward_direction
        *
        torso_delta
    )


    flex_mimic = max(
        0.0,
        flex_mimic
    )

    torso_mimic = max(
        0.0,
        torso_mimic
    )


    # ======================================================
    # Relative Specificity
    #
    # ไม่มีค่า Threshold ตายตัว
    #
    # Forward Head จริงต้องให้ Response
    # มากกว่า Distractor
    # ==========================================================

    flexion_specificity_pass = (
        main_response_median
        >
        flex_mimic
    )

    torso_specificity_pass = (
        main_response_median
        >
        torso_mimic
    )


    return {
        "main_response_median": (
            main_response_median
        ),

        "flex_normal": (
            flex_normal_value
        ),

        "flexion": (
            flex_value
        ),

        "flex_delta": (
            flex_delta
        ),

        "flex_mimic": (
            flex_mimic
        ),

        "torso_normal": (
            torso_normal_value
        ),

        "torso_lean": (
            torso_value
        ),

        "torso_delta": (
            torso_delta
        ),

        "torso_mimic": (
            torso_mimic
        ),

        "flexion_specificity_pass": (
            flexion_specificity_pass
        ),

        "torso_specificity_pass": (
            torso_specificity_pass
        ),
    }


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(results):

    print()
    print()
    print(
        "##################################################"
    )

    print(
        "POSTGUARD FORWARD HEAD FINAL VALIDATION REPORT"
    )

    print(
        "##################################################"
    )


    # ======================================================
    # Main Test
    # ==========================================================

    reports = analyse_main_test(
        results
    )


    for report in reports:

        print()
        print(
            f"ROUND {report['round']}"
        )

        print(
            "------------------------------------------"
        )

        print(
            "Normal 1:",
            f"{report['normal_1']:+.4f}"
        )

        print(
            "Normal 2:",
            f"{report['normal_2']:+.4f}"
        )

        print(
            "Normal Reference:",
            f"{report['normal_reference']:+.4f}"
        )

        print(
            "Forward Head:",
            f"{report['forward']:+.4f}"
        )

        print(
            "Forward Delta:",
            f"{report['forward_delta']:+.4f}"
        )


        print()

        print(
            "State Separation:",
            (
                "PASS"
                if report[
                    "separated"
                ]
                else "FAIL"
            )
        )


        direction = (
            report[
                "direction"
            ]
        )

        if direction > 0:

            direction_text = (
                "POSITIVE (+)"
            )

        elif direction < 0:

            direction_text = (
                "NEGATIVE (-)"
            )

        else:

            direction_text = (
                "NOT SEPARATED"
            )


        print(
            "Observed Direction:",
            direction_text
        )


        print()

        print(
            "Forward Head Std:",
            f"{report['forward_std']:.4f}"
        )

        print(
            "Normal 1 Std:",
            f"{report['normal_1_std']:.4f}"
        )

        print(
            "Normal 2 Std:",
            f"{report['normal_2_std']:.4f}"
        )


        print()

        print(
            "Neck Pitch Delta during Forward Head:",
            f"{report['pitch_delta']:+.3f} deg",
            "(DIAGNOSTIC)"
        )


        print()

        print(
            "Normal Return Error:",
            f"{report['normal_return_error']:.4f}",
            "(DIAGNOSTIC ONLY)"
        )


    # ======================================================
    # Direction Consistency
    # ==========================================================

    forward_direction = (
        determine_forward_direction(
            reports
        )
    )


    separation_count = sum(
        1
        for report in reports
        if report["separated"]
    )


    print()
    print(
        "=================================================="
    )

    print(
        "State Separation:",
        f"{separation_count}/3"
    )


    if forward_direction == 1:

        print(
            "Direction Consistency: 3/3"
        )

        print(
            "Observed Convention:"
        )

        print(
            "  Forward Head -> Metric increases (+)"
        )


    elif forward_direction == -1:

        print(
            "Direction Consistency: 3/3"
        )

        print(
            "Observed Convention:"
        )

        print(
            "  Forward Head -> Metric decreases (-)"
        )


    else:

        print(
            "Direction Consistency: FAIL"
        )

        print(
            "No stable Forward Head direction."
        )


    # ======================================================
    # Distractor Analysis
    # ==========================================================

    distractor = None


    if (
        forward_direction != 0
        and
        len(reports) == 3
    ):

        distractor = (
            analyse_distractors(
                results,
                forward_direction,
                reports,
            )
        )


    print()
    print(
        "=================================================="
    )

    print(
        "DISTRACTOR / SPECIFICITY CHECK"
    )

    print(
        "=================================================="
    )


    if distractor is None:

        print(
            "Distractor analysis unavailable."
        )

    else:

        print(
            "Median true Forward Head response:",
            f"{distractor['main_response_median']:.4f}"
        )


        print()

        print(
            "Flexion distractor:"
        )

        print(
            "  Normal:",
            f"{distractor['flex_normal']:+.4f}"
        )

        print(
            "  Flexion:",
            f"{distractor['flexion']:+.4f}"
        )

        print(
            "  Delta:",
            f"{distractor['flex_delta']:+.4f}"
        )

        print(
            "  Mimic response:",
            f"{distractor['flex_mimic']:.4f}"
        )

        print(
            "  Specificity:",
            (
                "PASS"
                if distractor[
                    "flexion_specificity_pass"
                ]
                else "NEEDS REVIEW"
            )
        )


        print()

        print(
            "Torso lean distractor:"
        )

        print(
            "  Normal:",
            f"{distractor['torso_normal']:+.4f}"
        )

        print(
            "  Torso Lean:",
            f"{distractor['torso_lean']:+.4f}"
        )

        print(
            "  Delta:",
            f"{distractor['torso_delta']:+.4f}"
        )

        print(
            "  Mimic response:",
            f"{distractor['torso_mimic']:.4f}"
        )

        print(
            "  Specificity:",
            (
                "PASS"
                if distractor[
                    "torso_specificity_pass"
                ]
                else "NEEDS REVIEW"
            )
        )


    # ======================================================
    # Final Decision
    # ==========================================================

    main_pass = (
        len(reports) == 3
        and
        separation_count == 3
        and
        forward_direction != 0
    )


    specificity_pass = (
        distractor is not None
        and
        distractor[
            "flexion_specificity_pass"
        ]
        and
        distractor[
            "torso_specificity_pass"
        ]
    )


    final_pass = (
        main_pass
        and
        specificity_pass
    )


    print()
    print(
        "=================================================="
    )


    if final_pass:

        print(
            "FORWARD HEAD DETECTION VALIDATION: PASS"
        )

        print()

        print(
            "Validated:"
        )

        print(
            "  - Direction consistency"
        )

        print(
            "  - State separation"
        )

        print(
            "  - Repeatability across 3 rounds"
        )

        print(
            "  - Relative specificity vs Flexion"
        )

        print(
            "  - Relative specificity vs Torso Lean"
        )


        print()

        print(
            "Not yet validated:"
        )

        print(
            "  - Absolute physical distance"
        )

        print(
            "  - Clinical threshold"
        )

        print(
            "  - Risk threshold"
        )

        print(
            "  - RULA scoring"
        )

    else:

        print(
            "FORWARD HEAD DETECTION VALIDATION:"
            " NEEDS REVIEW"
        )

        print()

        print(
            "Do NOT promote Forward Head "
            "to validated_prototype yet."
        )


    print(
        "=================================================="
    )


    return final_pass


# ==========================================================
# Save CSV
# ==========================================================

def save_results_to_csv(results):

    results_dir = (
        CAMERA_CARD_DIR
        /
        "mediapipe_detection"
        /
        "tests"
        /
        "results"
    )

    results_dir.mkdir(
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
        results_dir
        /
        (
            "forward_head_final_"
            +
            timestamp
            +
            ".csv"
        )
    )


    fieldnames = [
        "type",
        "round",
        "state",
        "samples",

        "forward_head_median",
        "forward_head_mean",
        "forward_head_std",
        "forward_head_min",
        "forward_head_max",

        "pitch_median",
        "pitch_mean",
        "pitch_std",

        "eye_distance_median",

        "nose_z_median",
        "shoulder_mid_z_median",
    ]


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )

        writer.writeheader()


        for item in results:

            summary = (
                item["summary"]
            )


            eye_distance_median = None

            if summary[
                "eye_distance"
            ] is not None:

                eye_distance_median = (
                    summary[
                        "eye_distance"
                    ][
                        "median"
                    ]
                )


            nose_z_median = None

            if summary[
                "nose_z"
            ] is not None:

                nose_z_median = (
                    summary[
                        "nose_z"
                    ][
                        "median"
                    ]
                )


            shoulder_mid_z_median = None

            if summary[
                "shoulder_mid_z"
            ] is not None:

                shoulder_mid_z_median = (
                    summary[
                        "shoulder_mid_z"
                    ][
                        "median"
                    ]
                )


            writer.writerow(
                {
                    "type": (
                        item["type"]
                    ),

                    "round": (
                        item["round"]
                    ),

                    "state": (
                        item["state"]
                    ),

                    "samples": (
                        summary["samples"]
                    ),

                    "forward_head_median": (
                        summary[
                            "forward_head"
                        ][
                            "median"
                        ]
                    ),

                    "forward_head_mean": (
                        summary[
                            "forward_head"
                        ][
                            "mean"
                        ]
                    ),

                    "forward_head_std": (
                        summary[
                            "forward_head"
                        ][
                            "std"
                        ]
                    ),

                    "forward_head_min": (
                        summary[
                            "forward_head"
                        ][
                            "min"
                        ]
                    ),

                    "forward_head_max": (
                        summary[
                            "forward_head"
                        ][
                            "max"
                        ]
                    ),

                    "pitch_median": (
                        summary[
                            "pitch"
                        ][
                            "median"
                        ]
                    ),

                    "pitch_mean": (
                        summary[
                            "pitch"
                        ][
                            "mean"
                        ]
                    ),

                    "pitch_std": (
                        summary[
                            "pitch"
                        ][
                            "std"
                        ]
                    ),

                    "eye_distance_median": (
                        eye_distance_median
                    ),

                    "nose_z_median": (
                        nose_z_median
                    ),

                    "shoulder_mid_z_median": (
                        shoulder_mid_z_median
                    ),
                }
            )


    print()
    print(
        "Results saved:"
    )

    print(
        output_path
    )

    return output_path


# ==========================================================
# State Instruction
# ==========================================================

def get_instruction(state):

    if state in (
        "NORMAL_1",
        "NORMAL_2",
    ):

        return (
            "Sit naturally and look straight"
        )


    if state == "FORWARD_HEAD":

        return (
            "Move HEAD forward, keep torso and pitch stable"
        )


    if state == "FLEXION_NORMAL":

        return (
            "Return to natural straight posture"
        )


    if state == "FLEXION_DISTRACTOR":

        return (
            "Bend neck DOWN, do NOT intentionally push head forward"
        )


    if state == "TORSO_NORMAL":

        return (
            "Return to natural straight posture"
        )


    if state == "TORSO_LEAN_DISTRACTOR":

        return (
            "Lean whole torso forward, keep neck neutral"
        )


    return state


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # Camera
    # ==========================================================

    capture = cv2.VideoCapture(
        CAMERA_INDEX
    )


    if not capture.isOpened():

        raise RuntimeError(
            "Cannot open webcam"
        )


    capture.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH
    )

    capture.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT
    )


    # ======================================================
    # Detection Pipeline
    # ==========================================================

    pipeline = (
        DetectionPipeline()
    )


    # ======================================================
    # Window
    # ==========================================================

    cv2.namedWindow(
        WINDOW_NAME,
        cv2.WINDOW_NORMAL
    )

    cv2.resizeWindow(
        WINDOW_NAME,
        CAMERA_WIDTH,
        CAMERA_HEIGHT
    )


    # ======================================================
    # Runtime
    # ==========================================================

    test_index = 0

    collecting = False

    collection_started_at = None

    current_samples = []

    results = []

    test_complete = False

    final_report_printed = False


    # ======================================================
    # Console Instructions
    # ==========================================================

    print()
    print(
        "=============================================="
    )

    print(
        "POSTGUARD FORWARD HEAD FINAL VALIDATION"
    )

    print(
        "=============================================="
    )

    print()

    print(
        "PART 1:"
    )

    print(
        "3 rounds of:"
    )

    print(
        "NORMAL -> FORWARD HEAD -> NORMAL"
    )

    print()

    print(
        "PART 2:"
    )

    print(
        "Distractor tests:"
    )

    print(
        "- FLEXION"
    )

    print(
        "- TORSO LEAN"
    )

    print()

    print(
        "SPACE = Capture current state"
    )

    print(
        "R     = Reset test"
    )

    print(
        "Q/ESC = Quit"
    )

    print()


    try:

        while True:

            # ==================================================
            # Camera
            # ==========================================================

            success, raw_frame = (
                capture.read()
            )


            if (
                not success
                or
                raw_frame is None
            ):

                print(
                    "Cannot read camera frame"
                )

                break


            timestamp = (
                time.perf_counter()
            )


            # ==================================================
            # Detection
            #
            # IMPORTANT:
            # Unmirrored frame
            # ==========================================================

            detection = (
                pipeline.process_frame(
                    raw_frame,
                    timestamp=timestamp
                )
            )


            # ==================================================
            # Forward Head
            # ==========================================================

            forward_feature = (
                detection[
                    "features"
                ][
                    "forward_head"
                ]
            )


            # ==================================================
            # Neck Pitch
            # ==========================================================

            pitch_feature = (
                detection[
                    "features"
                ][
                    "neck_flexion"
                ]
            )


            # ==================================================
            # Eye Distance
            # ==========================================================

            distance_feature = (
                detection[
                    "features"
                ][
                    "eye_distance"
                ]
            )


            # ==================================================
            # Current Values
            # ==========================================================

            current_forward = None

            current_pitch = None

            current_eye_distance = None

            current_nose_z = None

            current_shoulder_mid_z = None


            if forward_feature.get(
                "valid",
                False
            ):

                current_forward = (
                    forward_feature[
                        "value"
                    ]
                )


                extra = (
                    forward_feature.get(
                        "extra",
                        {}
                    )
                )


                current_nose_z = (
                    extra.get(
                        "nose_z"
                    )
                )


                current_shoulder_mid_z = (
                    extra.get(
                        "shoulder_mid_z"
                    )
                )


            if pitch_feature.get(
                "valid",
                False
            ):

                current_pitch = (
                    pitch_feature[
                        "value"
                    ]
                )


            if distance_feature.get(
                "valid",
                False
            ):

                current_eye_distance = (
                    distance_feature[
                        "value"
                    ]
                )


            # ==================================================
            # Collect Samples
            # ==========================================================

            if collecting:

                elapsed = (
                    timestamp
                    -
                    collection_started_at
                )


                # ----------------------------------------------
                # Forward Head + Pitch ต้อง valid
                #
                # Eye distance เป็น Diagnostic
                # ถ้าขาดยังเก็บได้
                # ----------------------------------------------

                if (
                    current_forward is not None
                    and
                    current_pitch is not None
                ):

                    current_samples.append(
                        {
                            "forward_head": float(
                                current_forward
                            ),

                            "pitch": float(
                                current_pitch
                            ),

                            "eye_distance": (
                                float(
                                    current_eye_distance
                                )
                                if current_eye_distance
                                is not None
                                else None
                            ),

                            "nose_z": (
                                float(
                                    current_nose_z
                                )
                                if current_nose_z
                                is not None
                                else None
                            ),

                            "shoulder_mid_z": (
                                float(
                                    current_shoulder_mid_z
                                )
                                if current_shoulder_mid_z
                                is not None
                                else None
                            ),
                        }
                    )


                # ----------------------------------------------
                # Finish Capture
                # ----------------------------------------------

                if (
                    elapsed
                    >=
                    SAMPLE_DURATION_SECONDS
                ):

                    step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    if (
                        len(current_samples)
                        <
                        MIN_VALID_SAMPLES
                    ):

                        print()
                        print(
                            "CAPTURE FAILED"
                        )

                        print(
                            "Valid samples:",
                            len(
                                current_samples
                            )
                        )

                        print(
                            "Required:",
                            MIN_VALID_SAMPLES
                        )

                        print(
                            "Repeat the same state."
                        )


                        collecting = False

                        current_samples = []


                    else:

                        summary = (
                            summarize_samples(
                                current_samples
                            )
                        )


                        results.append(
                            {
                                "type": (
                                    step[
                                        "type"
                                    ]
                                ),

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
                        )


                        # ======================================
                        # Print State
                        # ======================================

                        print()
                        print(
                            "=========================================="
                        )

                        print(
                            "STATE:",
                            step[
                                "state"
                            ]
                        )

                        if (
                            step[
                                "type"
                            ]
                            ==
                            "MAIN"
                        ):

                            print(
                                "ROUND:",
                                step[
                                    "round"
                                ]
                            )


                        print(
                            "Samples:",
                            summary[
                                "samples"
                            ]
                        )


                        print()

                        print(
                            "Forward Head Median:",
                            f"{summary['forward_head']['median']:+.4f}"
                        )

                        print(
                            "Forward Head Mean:",
                            f"{summary['forward_head']['mean']:+.4f}"
                        )

                        print(
                            "Forward Head Std:",
                            f"{summary['forward_head']['std']:.4f}"
                        )


                        print()

                        print(
                            "Pitch Median:",
                            f"{summary['pitch']['median']:+.3f} deg"
                        )


                        if (
                            summary[
                                "eye_distance"
                            ]
                            is not None
                        ):

                            print(
                                "Eye Distance Median:",
                                f"{summary['eye_distance']['median']:.3f} px"
                            )


                        print(
                            "=========================================="
                        )


                        # ======================================
                        # Next Test
                        # ======================================

                        test_index += 1

                        collecting = False

                        current_samples = []


                        if (
                            test_index
                            >=
                            len(
                                TEST_SEQUENCE
                            )
                        ):

                            test_complete = True


            # ==================================================
            # Display
            #
            # Mirror only for display
            # ==========================================================

            display = cv2.flip(
                raw_frame.copy(),
                1
            )


            # ==================================================
            # Header
            # ==========================================================

            put(
                display,
                (
                    "POSTGUARD - "
                    "FORWARD HEAD FINAL TEST"
                ),
                30,
                CYAN,
                scale=0.7,
                thickness=2,
            )


            # ==================================================
            # State
            # ==========================================================

            if not test_complete:

                step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                if step[
                    "type"
                ] == "MAIN":

                    put(
                        display,
                        (
                            f"ROUND: "
                            f"{step['round']} / 3"
                        ),
                        65,
                        WHITE,
                    )

                else:

                    put(
                        display,
                        "DISTRACTOR TEST",
                        65,
                        YELLOW,
                    )


                put(
                    display,
                    (
                        f"STATE: "
                        f"{step['state']}"
                    ),
                    95,
                    YELLOW,
                )


                put(
                    display,
                    get_instruction(
                        step[
                            "state"
                        ]
                    ),
                    125,
                    WHITE,
                )


            else:

                put(
                    display,
                    "TEST COMPLETE",
                    85,
                    GREEN,
                    scale=0.8,
                    thickness=2,
                )


            # ==================================================
            # Live Values
            # ==========================================================

            y = 180


            if current_forward is not None:

                put(
                    display,
                    (
                        "Forward Head: "
                        f"{current_forward:+.4f}"
                    ),
                    y,
                    GREEN,
                )

            else:

                put(
                    display,
                    "Forward Head: INVALID",
                    y,
                    RED,
                )


            y += 30


            if current_pitch is not None:

                put(
                    display,
                    (
                        "Neck Pitch: "
                        f"{current_pitch:+.3f} deg"
                    ),
                    y,
                    WHITE,
                )

            else:

                put(
                    display,
                    "Neck Pitch: INVALID",
                    y,
                    RED,
                )


            y += 30


            if current_eye_distance is not None:

                put(
                    display,
                    (
                        "Eye Distance: "
                        f"{current_eye_distance:.2f} px"
                    ),
                    y,
                    WHITE,
                )


            # ==================================================
            # Collection Progress
            # ==========================================================

            if collecting:

                elapsed = (
                    timestamp
                    -
                    collection_started_at
                )

                progress = min(
                    elapsed
                    /
                    SAMPLE_DURATION_SECONDS,
                    1.0
                )


                y += 55


                put(
                    display,
                    "COLLECTING...",
                    y,
                    GREEN,
                    scale=0.7,
                    thickness=2,
                )


                y += 30


                put(
                    display,
                    (
                        f"Progress: "
                        f"{progress * 100:.0f}%"
                    ),
                    y,
                    GREEN,
                )


                y += 30


                put(
                    display,
                    (
                        "Valid samples: "
                        f"{len(current_samples)}"
                    ),
                    y,
                    GREEN,
                )


            # ==================================================
            # Controls
            # ==========================================================

            help_y = (
                display.shape[0]
                -
                40
            )


            if not collecting:

                put(
                    display,
                    (
                        "SPACE: Capture | "
                        "R: Reset | "
                        "Q/ESC: Quit"
                    ),
                    help_y,
                    WHITE,
                )

            else:

                put(
                    display,
                    (
                        "Hold posture until capture completes"
                    ),
                    help_y,
                    YELLOW,
                )


            cv2.imshow(
                WINDOW_NAME,
                display
            )


            # ==================================================
            # Final Report
            # ==========================================================

            if (
                test_complete
                and
                not final_report_printed
            ):

                final_pass = (
                    print_final_report(
                        results
                    )
                )


                save_results_to_csv(
                    results
                )


                final_report_printed = True


                if final_pass:

                    print()
                    print(
                        "RESULT:"
                    )

                    print(
                        "Forward Head is ready "
                        "for validated_prototype."
                    )

                else:

                    print()
                    print(
                        "RESULT:"
                    )

                    print(
                        "Forward Head needs review."
                    )


            # ==================================================
            # Keyboard
            # ==========================================================

            key = (
                cv2.waitKey(1)
                &
                0xFF
            )


            # --------------------------------------------------
            # Start Capture
            # --------------------------------------------------

            if (
                key == 32
                and
                not collecting
                and
                not test_complete
            ):

                collecting = True

                collection_started_at = (
                    time.perf_counter()
                )

                current_samples = []


                step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print()
                print(
                    "CAPTURE START"
                )

                print(
                    "State:",
                    step[
                        "state"
                    ]
                )

                if step[
                    "type"
                ] == "MAIN":

                    print(
                        "Round:",
                        step[
                            "round"
                        ]
                    )


            # --------------------------------------------------
            # Reset
            # --------------------------------------------------

            elif key in (
                ord("r"),
                ord("R"),
            ):

                test_index = 0

                collecting = False

                collection_started_at = None

                current_samples = []

                results = []

                test_complete = False

                final_report_printed = False


                print()
                print(
                    "TEST RESET"
                )
                print()


            # --------------------------------------------------
            # Quit
            # --------------------------------------------------

            elif key in (
                ord("q"),
                ord("Q"),
                27,
            ):

                break


    finally:

        pipeline.close()

        capture.release()

        cv2.destroyAllWindows()


# ==========================================================
# Entry Point
# ==========================================================

if __name__ == "__main__":

    main()