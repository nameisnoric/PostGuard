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
    "PostGuard - Neck Flexion Final Test"
)


# ==========================================================
# Capture Settings
#
# 2 วินาทีต่อหนึ่ง State
#
# MIN_VALID_SAMPLES = 15
#
# เป็นเพียง Quality Control ว่า Capture มีข้อมูลเพียงพอ
# ไม่ใช่ Risk / RULA / Medical Threshold
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# Test Sequence
#
# ทำทั้งหมด 3 รอบ
#
# ROUND:
# NORMAL_1
# FLEXION
# NORMAL_2
# EXTENSION
#
# รวม 12 Capture States
# ==========================================================

TEST_SEQUENCE = []

for round_number in range(1, 4):

    TEST_SEQUENCE.extend(
        [
            {
                "round": round_number,
                "state": "NORMAL_1",
            },
            {
                "round": round_number,
                "state": "FLEXION",
            },
            {
                "round": round_number,
                "state": "NORMAL_2",
            },
            {
                "round": round_number,
                "state": "EXTENSION",
            },
        ]
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
    """
    วาดข้อความบน OpenCV Frame
    """

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
# Statistical Summary
# ==========================================================

def summarize_values(values):
    """
    สรุปค่าจากหลาย Frame

    ใช้:
    - Median
    - Mean
    - Standard Deviation
    - Min
    - Max

    Median ใช้เป็นค่าหลักในการเปรียบเทียบ
    เพราะทนต่อ Outlier ได้ดีกว่า Frame เดียว
    """

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
# Summarize Capture Samples
# ==========================================================

def summarize_samples(samples):
    """
    แยก Pitch / Yaw / Roll
    แล้วสร้าง Summary
    """

    pitch_values = [
        sample["pitch"]
        for sample in samples
    ]

    yaw_values = [
        sample["yaw"]
        for sample in samples
    ]

    roll_values = [
        sample["roll"]
        for sample in samples
    ]

    return {
        "samples": len(samples),

        "pitch": summarize_values(
            pitch_values
        ),

        "yaw": summarize_values(
            yaw_values
        ),

        "roll": summarize_values(
            roll_values
        ),
    }


# ==========================================================
# Get Result of One State
# ==========================================================

def get_state_result(
    results,
    round_number,
    state,
):
    """
    ค้นหา Result ตาม:
    - Round
    - State
    """

    for item in results:

        if (
            item["round"] == round_number
            and
            item["state"] == state
        ):
            return item

    return None


# ==========================================================
# Analyse One Round
# ==========================================================

def analyse_round(
    results,
    round_number,
):
    """
    วิเคราะห์ 1 Round

    IMPORTANT:
    ไม่มี Threshold 10° หรือ 5° แล้ว

    เราตรวจ:
    1. Flexion อยู่เหนือ Neutral ทั้งสองช่วงหรือไม่
    2. Extension อยู่ต่ำกว่า Neutral ทั้งสองช่วงหรือไม่
    3. Pitch เป็นแกนหลักเหนือ Yaw/Roll หรือไม่
    4. Normal Return Error รายงานเป็น Diagnostic
    """

    normal_1 = get_state_result(
        results,
        round_number,
        "NORMAL_1"
    )

    flexion = get_state_result(
        results,
        round_number,
        "FLEXION"
    )

    normal_2 = get_state_result(
        results,
        round_number,
        "NORMAL_2"
    )

    extension = get_state_result(
        results,
        round_number,
        "EXTENSION"
    )


    # ------------------------------------------------------
    # ต้องมีครบทั้ง 4 State
    # ------------------------------------------------------

    if (
        normal_1 is None
        or flexion is None
        or normal_2 is None
        or extension is None
    ):
        return None


    # ======================================================
    # Pitch Median
    # ==========================================================

    normal_1_pitch = (
        normal_1["summary"]
        ["pitch"]
        ["median"]
    )

    normal_2_pitch = (
        normal_2["summary"]
        ["pitch"]
        ["median"]
    )

    flexion_pitch = (
        flexion["summary"]
        ["pitch"]
        ["median"]
    )

    extension_pitch = (
        extension["summary"]
        ["pitch"]
        ["median"]
    )


    # ======================================================
    # Neutral Reference
    #
    # ใช้ Median ของ Normal 1 / Normal 2
    #
    # เป็น reference สำหรับ Test นี้เท่านั้น
    # ยังไม่ใช่ Personal Baseline
    # ==========================================================

    normal_reference = float(
        np.median(
            [
                normal_1_pitch,
                normal_2_pitch,
            ]
        )
    )


    # ======================================================
    # Pitch Delta
    #
    # ใช้เพื่อรายงาน Response Magnitude
    #
    # ไม่มี Threshold 10° แล้ว
    # ==========================================================

    flexion_delta = (
        flexion_pitch
        -
        normal_reference
    )

    extension_delta = (
        extension_pitch
        -
        normal_reference
    )


    # ======================================================
    # Normal Return Error
    #
    # IMPORTANT:
    #
    # รายงานเท่านั้น
    #
    # ไม่ใช้เป็น Hard PASS / FAIL
    # เพราะมี Human Posture Repeatability ปนอยู่
    # ==========================================================

    normal_return_error = abs(
        normal_2_pitch
        -
        normal_1_pitch
    )


    # ======================================================
    # Normal Pitch Range
    #
    # เรามี Neutral สอง Capture
    #
    # Flexion ควรอยู่เหนือ Neutral ทั้งสอง
    # Extension ควรอยู่ต่ำกว่า Neutral ทั้งสอง
    #
    # วิธีนี้ไม่ต้องตั้ง "10°"
    # ==========================================================

    normal_pitch_max = max(
        normal_1_pitch,
        normal_2_pitch,
    )

    normal_pitch_min = min(
        normal_1_pitch,
        normal_2_pitch,
    )


    # ======================================================
    # Direction / Separation
    #
    # Flexion:
    # ต้อง Positive direction
    # และสูงกว่า Neutral ทั้งสอง Capture
    #
    # Extension:
    # ต้อง Negative direction
    # และต่ำกว่า Neutral ทั้งสอง Capture
    # ==========================================================

    flexion_separated = (
        flexion_pitch
        >
        normal_pitch_max
    )

    extension_separated = (
        extension_pitch
        <
        normal_pitch_min
    )

    direction_pass = (
        flexion_separated
        and
        extension_separated
    )


    # ======================================================
    # Yaw Diagnostic
    # ==========================================================

    normal_1_yaw = (
        normal_1["summary"]
        ["yaw"]
        ["median"]
    )

    normal_2_yaw = (
        normal_2["summary"]
        ["yaw"]
        ["median"]
    )

    normal_yaw = float(
        np.median(
            [
                normal_1_yaw,
                normal_2_yaw,
            ]
        )
    )

    flexion_yaw = (
        flexion["summary"]
        ["yaw"]
        ["median"]
    )

    extension_yaw = (
        extension["summary"]
        ["yaw"]
        ["median"]
    )

    flexion_yaw_delta = (
        flexion_yaw
        -
        normal_yaw
    )

    extension_yaw_delta = (
        extension_yaw
        -
        normal_yaw
    )


    # ======================================================
    # Roll Diagnostic
    # ==========================================================

    normal_1_roll = (
        normal_1["summary"]
        ["roll"]
        ["median"]
    )

    normal_2_roll = (
        normal_2["summary"]
        ["roll"]
        ["median"]
    )

    normal_roll = float(
        np.median(
            [
                normal_1_roll,
                normal_2_roll,
            ]
        )
    )

    flexion_roll = (
        flexion["summary"]
        ["roll"]
        ["median"]
    )

    extension_roll = (
        extension["summary"]
        ["roll"]
        ["median"]
    )

    flexion_roll_delta = (
        flexion_roll
        -
        normal_roll
    )

    extension_roll_delta = (
        extension_roll
        -
        normal_roll
    )


    # ======================================================
    # Pitch Dominance
    #
    # ถ้าทดสอบ "ก้ม/เงย"
    # การเปลี่ยน Pitch ควรเด่นกว่า
    # Yaw และ Roll
    #
    # นี่เป็น Axis Consistency Check
    # ไม่ใช่ Risk Threshold
    # ==========================================================

    flexion_pitch_dominant = (
        abs(flexion_delta)
        >
        max(
            abs(flexion_yaw_delta),
            abs(flexion_roll_delta),
        )
    )

    extension_pitch_dominant = (
        abs(extension_delta)
        >
        max(
            abs(extension_yaw_delta),
            abs(extension_roll_delta),
        )
    )


    # ======================================================
    # Within-State Stability
    #
    # รายงาน Standard Deviation
    # ไม่กำหนด Hard Threshold ตอนนี้
    # ==========================================================

    normal_1_std = (
        normal_1["summary"]
        ["pitch"]
        ["std"]
    )

    normal_2_std = (
        normal_2["summary"]
        ["pitch"]
        ["std"]
    )

    flexion_std = (
        flexion["summary"]
        ["pitch"]
        ["std"]
    )

    extension_std = (
        extension["summary"]
        ["pitch"]
        ["std"]
    )


    # ======================================================
    # Round PASS
    #
    # ใช้เฉพาะสิ่งที่ Test นี้พิสูจน์โดยตรง:
    #
    # - Direction / State Separation
    # - Pitch Axis Dominance
    #
    # Normal Return ไม่ใช่ Hard Gate
    # Response Degrees ไม่มี Threshold
    # ==========================================================

    round_pass = (
        direction_pass
        and
        flexion_pitch_dominant
        and
        extension_pitch_dominant
    )


    return {
        "round": round_number,

        # Neutral
        "normal_1_pitch": normal_1_pitch,
        "normal_2_pitch": normal_2_pitch,
        "normal_reference": normal_reference,
        "normal_return_error": normal_return_error,

        # State variability
        "normal_1_std": normal_1_std,
        "normal_2_std": normal_2_std,
        "flexion_std": flexion_std,
        "extension_std": extension_std,

        # Flexion
        "flexion_pitch": flexion_pitch,
        "flexion_delta": flexion_delta,
        "flexion_separated": flexion_separated,

        # Extension
        "extension_pitch": extension_pitch,
        "extension_delta": extension_delta,
        "extension_separated": extension_separated,

        # Direction
        "direction_pass": direction_pass,

        # Yaw diagnostic
        "flexion_yaw_delta": flexion_yaw_delta,
        "extension_yaw_delta": extension_yaw_delta,

        # Roll diagnostic
        "flexion_roll_delta": flexion_roll_delta,
        "extension_roll_delta": extension_roll_delta,

        # Axis dominance
        "flexion_pitch_dominant": (
            flexion_pitch_dominant
        ),

        "extension_pitch_dominant": (
            extension_pitch_dominant
        ),

        # Final round
        "round_pass": round_pass,
    }


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(results):
    """
    สรุปผลทั้ง 3 รอบ
    """

    print()
    print()
    print(
        "##################################################"
    )
    print(
        "POSTGUARD NECK FLEXION / EXTENSION FINAL REPORT"
    )
    print(
        "##################################################"
    )


    reports = []

    for round_number in range(
        1,
        4
    ):

        report = analyse_round(
            results,
            round_number
        )

        if report is not None:
            reports.append(
                report
            )


    round_pass_count = 0
    direction_pass_count = 0
    pitch_dominance_count = 0


    # เก็บ Normal Return
    # เพื่อรายงาน Repeatability
    normal_return_errors = []


    # ======================================================
    # Print Each Round
    # ==========================================================

    for report in reports:

        print()
        print(
            f"ROUND {report['round']}"
        )

        print(
            "------------------------------------------"
        )


        # --------------------------------------------------
        # Neutral
        # --------------------------------------------------

        print(
            "Normal 1:",
            f"{report['normal_1_pitch']:+.3f} deg"
        )

        print(
            "Normal 2:",
            f"{report['normal_2_pitch']:+.3f} deg"
        )

        print(
            "Normal Reference:",
            f"{report['normal_reference']:+.3f} deg"
        )

        print(
            "Normal Return Error:",
            f"{report['normal_return_error']:.3f} deg",
            "(DIAGNOSTIC ONLY)"
        )


        normal_return_errors.append(
            report[
                "normal_return_error"
            ]
        )


        print()

        print(
            "Normal 1 Pitch Std:",
            f"{report['normal_1_std']:.3f} deg"
        )

        print(
            "Normal 2 Pitch Std:",
            f"{report['normal_2_std']:.3f} deg"
        )


        # --------------------------------------------------
        # Flexion
        # --------------------------------------------------

        print()
        print(
            "Flexion Pitch:",
            f"{report['flexion_pitch']:+.3f} deg"
        )

        print(
            "Flexion Delta:",
            f"{report['flexion_delta']:+.3f} deg"
        )

        print(
            "Flexion Pitch Std:",
            f"{report['flexion_std']:.3f} deg"
        )

        print(
            "Flexion separated from Neutral:",
            (
                "PASS"
                if report[
                    "flexion_separated"
                ]
                else "FAIL"
            )
        )

        print(
            "Flexion Pitch Dominant:",
            (
                "PASS"
                if report[
                    "flexion_pitch_dominant"
                ]
                else "FAIL"
            )
        )


        # --------------------------------------------------
        # Extension
        # --------------------------------------------------

        print()
        print(
            "Extension Pitch:",
            f"{report['extension_pitch']:+.3f} deg"
        )

        print(
            "Extension Delta:",
            f"{report['extension_delta']:+.3f} deg"
        )

        print(
            "Extension Pitch Std:",
            f"{report['extension_std']:.3f} deg"
        )

        print(
            "Extension separated from Neutral:",
            (
                "PASS"
                if report[
                    "extension_separated"
                ]
                else "FAIL"
            )
        )

        print(
            "Extension Pitch Dominant:",
            (
                "PASS"
                if report[
                    "extension_pitch_dominant"
                ]
                else "FAIL"
            )
        )


        # --------------------------------------------------
        # Direction
        # --------------------------------------------------

        print()

        print(
            "Direction:",
            (
                "PASS"
                if report[
                    "direction_pass"
                ]
                else "FAIL"
            )
        )

        print(
            "Observed Convention:"
        )

        print(
            "  FLEXION   -> Pitch increases"
        )

        print(
            "  EXTENSION -> Pitch decreases"
        )


        # --------------------------------------------------
        # Round
        # --------------------------------------------------

        print()

        print(
            "ROUND RESULT:",
            (
                "PASS"
                if report[
                    "round_pass"
                ]
                else "FAIL"
            )
        )


        # --------------------------------------------------
        # Counter
        # --------------------------------------------------

        if report[
            "round_pass"
        ]:
            round_pass_count += 1


        if report[
            "direction_pass"
        ]:
            direction_pass_count += 1


        if (
            report[
                "flexion_pitch_dominant"
            ]
            and
            report[
                "extension_pitch_dominant"
            ]
        ):
            pitch_dominance_count += 1


    # ======================================================
    # Neutral Diagnostic Summary
    # ==========================================================

    if normal_return_errors:

        normal_return_median = float(
            np.median(
                normal_return_errors
            )
        )

        normal_return_mean = float(
            np.mean(
                normal_return_errors
            )
        )

        normal_return_max = float(
            np.max(
                normal_return_errors
            )
        )

    else:

        normal_return_median = None
        normal_return_mean = None
        normal_return_max = None


    # ======================================================
    # Final Summary
    # ==========================================================

    print()
    print(
        "=================================================="
    )

    print(
        "Direction / Separation:",
        f"{direction_pass_count}/3"
    )

    print(
        "Pitch Dominance:",
        f"{pitch_dominance_count}/3"
    )

    print(
        "Full Detection Round:",
        f"{round_pass_count}/3"
    )


    print()
    print(
        "Neutral Return Diagnostic:"
    )

    if normal_return_median is not None:

        print(
            "  Median Error:",
            f"{normal_return_median:.3f} deg"
        )

        print(
            "  Mean Error:",
            f"{normal_return_mean:.3f} deg"
        )

        print(
            "  Maximum Error:",
            f"{normal_return_max:.3f} deg"
        )

        print(
            "  NOTE:"
        )

        print(
            "  Neutral Return is reported only."
        )

        print(
            "  It does NOT determine Detection PASS/FAIL."
        )


    # ======================================================
    # Final Decision
    # ==========================================================

    final_pass = (
        len(reports) == 3
        and
        round_pass_count == 3
    )


    print()
    print(
        "--------------------------------------------------"
    )


    if final_pass:

        print(
            "NECK FLEXION / EXTENSION DETECTION:"
            " PASS"
        )

        print()

        print(
            "LOCK DIRECTION CONVENTION:"
        )

        print(
            "  FLEXION   -> POSITIVE / Pitch increases"
        )

        print(
            "  EXTENSION -> NEGATIVE / Pitch decreases"
        )

        print()

        print(
            "This validates:"
        )

        print(
            "  - Direction"
        )

        print(
            "  - State separation"
        )

        print(
            "  - Axis consistency"
        )

        print()

        print(
            "This does NOT yet validate:"
        )

        print(
            "  - Absolute angular accuracy"
        )

        print(
            "  - RULA risk thresholds"
        )

        print(
            "  - Clinical accuracy"
        )

    else:

        print(
            "NECK FLEXION / EXTENSION DETECTION:"
            " NEEDS REVIEW"
        )

        print()

        print(
            "Do NOT promote candidate -> validated."
        )


    print(
        "=================================================="
    )


    return final_pass


# ==========================================================
# Save CSV
# ==========================================================

def save_results_to_csv(
    results
):
    """
    เก็บผล Capture ไว้เป็น Test Evidence
    """

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
            "neck_flexion_final_"
            +
            timestamp
            +
            ".csv"
        )
    )


    fieldnames = [
        "round",
        "state",
        "samples",

        "pitch_median",
        "pitch_mean",
        "pitch_std",
        "pitch_min",
        "pitch_max",

        "yaw_median",
        "yaw_mean",
        "yaw_std",

        "roll_median",
        "roll_mean",
        "roll_std",
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

            writer.writerow(
                {
                    "round": (
                        item["round"]
                    ),

                    "state": (
                        item["state"]
                    ),

                    "samples": (
                        summary["samples"]
                    ),

                    "pitch_median": (
                        summary["pitch"]
                        ["median"]
                    ),

                    "pitch_mean": (
                        summary["pitch"]
                        ["mean"]
                    ),

                    "pitch_std": (
                        summary["pitch"]
                        ["std"]
                    ),

                    "pitch_min": (
                        summary["pitch"]
                        ["min"]
                    ),

                    "pitch_max": (
                        summary["pitch"]
                        ["max"]
                    ),

                    "yaw_median": (
                        summary["yaw"]
                        ["median"]
                    ),

                    "yaw_mean": (
                        summary["yaw"]
                        ["mean"]
                    ),

                    "yaw_std": (
                        summary["yaw"]
                        ["std"]
                    ),

                    "roll_median": (
                        summary["roll"]
                        ["median"]
                    ),

                    "roll_mean": (
                        summary["roll"]
                        ["mean"]
                    ),

                    "roll_std": (
                        summary["roll"]
                        ["std"]
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

def get_instruction(
    state
):
    """
    ข้อความแนะนำผู้ทดสอบ
    """

    if state == "NORMAL_1":

        return (
            "Sit naturally and look straight forward"
        )

    if state == "NORMAL_2":

        return (
            "Return to your natural straight posture"
        )

    if state == "FLEXION":

        return (
            "Bend neck DOWN without turning/tilting"
        )

    if state == "EXTENSION":

        return (
            "Tilt head UP without turning/tilting"
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

    pipeline = DetectionPipeline()


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
    # Test Runtime
    # ==========================================================

    test_index = 0

    collecting = False

    collection_started_at = None

    current_samples = []

    results = []

    test_complete = False

    final_report_printed = False


    # ======================================================
    # Console
    # ==========================================================

    print()
    print(
        "=============================================="
    )

    print(
        "POSTGUARD NECK FLEXION / EXTENSION FINAL TEST"
    )

    print(
        "=============================================="
    )

    print()

    print(
        "Purpose:"
    )

    print(
        "- Validate direction"
    )

    print(
        "- Validate Flexion/Extension separation"
    )

    print(
        "- Validate Pitch axis dominance"
    )

    print()

    print(
        "NOTE:"
    )

    print(
        "No arbitrary 10-degree response threshold."
    )

    print(
        "No arbitrary 5-degree normal-return threshold."
    )

    print()

    print(
        "Normal-return error is DIAGNOSTIC ONLY."
    )

    print()

    print(
        "3 rounds"
    )

    print(
        "NORMAL -> FLEXION -> NORMAL -> EXTENSION"
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
            # Read Camera
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
            # Feature Results
            # ==========================================================

            neck_feature = (
                detection["features"]
                ["neck_flexion"]
            )

            yaw_feature = (
                detection["features"]
                ["head_yaw"]
            )

            roll_feature = (
                detection["features"]
                ["head_roll"]
            )


            current_pitch = None
            current_yaw = None
            current_roll = None


            if neck_feature.get(
                "valid",
                False
            ):

                current_pitch = (
                    neck_feature["value"]
                )


            if yaw_feature.get(
                "valid",
                False
            ):

                current_yaw = (
                    yaw_feature["value"]
                )


            if roll_feature.get(
                "valid",
                False
            ):

                current_roll = (
                    roll_feature["value"]
                )


            # ==================================================
            # Collect
            # ==========================================================

            if collecting:

                elapsed = (
                    timestamp
                    -
                    collection_started_at
                )


                # ----------------------------------------------
                # เก็บเฉพาะ Frame ที่ครบ
                # Pitch + Yaw + Roll
                # ----------------------------------------------

                if (
                    current_pitch is not None
                    and
                    current_yaw is not None
                    and
                    current_roll is not None
                ):

                    current_samples.append(
                        {
                            "pitch": float(
                                current_pitch
                            ),

                            "yaw": float(
                                current_yaw
                            ),

                            "roll": float(
                                current_roll
                            ),
                        }
                    )


                # ----------------------------------------------
                # Complete Capture
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


                    # ------------------------------------------
                    # Sample Count
                    # ------------------------------------------

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
                            "Not enough valid samples:"
                        )

                        print(
                            len(current_samples)
                        )

                        print(
                            "Required:",
                            MIN_VALID_SAMPLES
                        )

                        print()
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
                                "round": (
                                    step["round"]
                                ),

                                "state": (
                                    step["state"]
                                ),

                                "summary": (
                                    summary
                                ),
                            }
                        )


                        print()
                        print(
                            "=========================================="
                        )

                        print(
                            f"ROUND {step['round']}"
                        )

                        print(
                            f"STATE {step['state']}"
                        )

                        print(
                            "Samples:",
                            summary["samples"]
                        )

                        print()

                        print(
                            "Pitch Median:",
                            f"{summary['pitch']['median']:+.3f} deg"
                        )

                        print(
                            "Pitch Mean:",
                            f"{summary['pitch']['mean']:+.3f} deg"
                        )

                        print(
                            "Pitch Std:",
                            f"{summary['pitch']['std']:.3f} deg"
                        )

                        print()

                        print(
                            "Yaw Median:",
                            f"{summary['yaw']['median']:+.3f} deg"
                        )

                        print(
                            "Roll Median:",
                            f"{summary['roll']['median']:+.3f} deg"
                        )

                        print(
                            "=========================================="
                        )


                        # --------------------------------------
                        # Next State
                        # --------------------------------------

                        test_index += 1

                        collecting = False

                        current_samples = []


                        if (
                            test_index
                            >=
                            len(TEST_SEQUENCE)
                        ):

                            test_complete = True


            # ==================================================
            # Display
            #
            # Mirror only for UI
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
                    "NECK FLEXION FINAL TEST"
                ),
                30,
                CYAN,
                scale=0.7,
                thickness=2,
            )


            # ==================================================
            # Current Test State
            # ==========================================================

            if not test_complete:

                step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )

                put(
                    display,
                    (
                        f"ROUND: "
                        f"{step['round']} / 3"
                    ),
                    65,
                    WHITE,
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
                        step["state"]
                    ),
                    125,
                    WHITE,
                )

            else:

                put(
                    display,
                    "TEST COMPLETE",
                    80,
                    GREEN,
                    scale=0.8,
                    thickness=2,
                )


            # ==================================================
            # Live Values
            # ==========================================================

            y = 175


            if current_pitch is not None:

                put(
                    display,
                    (
                        "Pitch: "
                        f"{current_pitch:+.3f} deg"
                    ),
                    y,
                    GREEN,
                )

            else:

                put(
                    display,
                    "Pitch: INVALID",
                    y,
                    RED,
                )


            y += 30


            if current_yaw is not None:

                put(
                    display,
                    (
                        "Yaw: "
                        f"{current_yaw:+.3f} deg"
                    ),
                    y,
                    WHITE,
                )

            else:

                put(
                    display,
                    "Yaw: INVALID",
                    y,
                    RED,
                )


            y += 30


            if current_roll is not None:

                put(
                    display,
                    (
                        "Roll: "
                        f"{current_roll:+.3f} deg"
                    ),
                    y,
                    WHITE,
                )

            else:

                put(
                    display,
                    "Roll: INVALID",
                    y,
                    RED,
                )


            # ==================================================
            # Collect Progress
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


                y += 50


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
                        "Hold posture until "
                        "capture completes"
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
                        "Neck Flexion / Extension "
                        "direction is ready to LOCK."
                    )

                else:

                    print()
                    print(
                        "RESULT:"
                    )

                    print(
                        "Do NOT lock the metric yet."
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
                    "Round:",
                    step["round"]
                )

                print(
                    "State:",
                    step["state"]
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