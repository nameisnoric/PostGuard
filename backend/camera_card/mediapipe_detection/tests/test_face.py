from pathlib import Path
import sys
import time
import csv
from datetime import datetime

import cv2
import numpy as np


# ==========================================================
# camera_card root
# ==========================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)


# ==========================================================
# เพิ่ม camera_card ลง Python Path
# ==========================================================

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

from mediapipe_detection.face.face_validator import (
    validate_head_orientation,
    validate_eye_points
)

from mediapipe_detection.face.face_orientation import (
    extract_face_orientation
)


# ==========================================================
# Face Model Path
# ==========================================================

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


# ==========================================================
# Repeatability Test Settings
#
# 2 วินาทีต่อท่า
#
# MIN_VALID_SAMPLES:
# ใช้ป้องกันกรณี Face หลุดเกือบตลอดช่วง Capture
#
# ไม่ใช่ Posture Threshold
# ไม่ใช่ Risk Threshold
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# Test Sequence
#
# 3 Rounds
#
# แต่ละ Round:
# Normal 1
# Flexion
# Normal 2
# Extension
#
# รวมทั้งหมด = 12 Capture States
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
# Axis Summary
# ==========================================================

def summarize_axis(
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
# Sample Summary
# ==========================================================

def summarize_samples(
    samples
):

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

        "samples": len(
            samples
        ),

        "pitch": summarize_axis(
            pitch_values
        ),

        "yaw": summarize_axis(
            yaw_values
        ),

        "roll": summarize_axis(
            roll_values
        ),
    }


# ==========================================================
# Print One State Result
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
        f"ROUND: {step['round']}"
    )

    print(
        f"STATE: {step['state']}"
    )

    print(
        f"VALID SAMPLES: {summary['samples']}"
    )

    print(
        "----------------------------------------"
    )


    # ======================================================
    # Pitch
    # ======================================================

    print(
        "Pitch"
    )

    print(
        "  Median:",
        f"{summary['pitch']['median']:+.3f} deg"
    )

    print(
        "  Mean  :",
        f"{summary['pitch']['mean']:+.3f} deg"
    )

    print(
        "  Std   :",
        f"{summary['pitch']['std']:.3f} deg"
    )


    # ======================================================
    # Yaw
    # ======================================================

    print(
        "Yaw"
    )

    print(
        "  Median:",
        f"{summary['yaw']['median']:+.3f} deg"
    )

    print(
        "  Mean  :",
        f"{summary['yaw']['mean']:+.3f} deg"
    )

    print(
        "  Std   :",
        f"{summary['yaw']['std']:.3f} deg"
    )


    # ======================================================
    # Roll
    # ======================================================

    print(
        "Roll"
    )

    print(
        "  Median:",
        f"{summary['roll']['median']:+.3f} deg"
    )

    print(
        "  Mean  :",
        f"{summary['roll']['mean']:+.3f} deg"
    )

    print(
        "  Std   :",
        f"{summary['roll']['std']:.3f} deg"
    )


    print(
        "========================================"
    )


# ==========================================================
# Get Round State
# ==========================================================

def get_round_state(
    results,
    round_number,
    state
):

    for item in results:

        if (
            item["round"] == round_number
            and item["state"] == state
        ):

            return item


    return None


# ==========================================================
# Analyse Repeatability
# ==========================================================

def analyse_repeatability(
    results
):

    round_reports = []


    for round_number in range(
        1,
        4
    ):

        normal_1 = get_round_state(
            results,
            round_number,
            "NORMAL_1"
        )


        flexion = get_round_state(
            results,
            round_number,
            "FLEXION"
        )


        normal_2 = get_round_state(
            results,
            round_number,
            "NORMAL_2"
        )


        extension = get_round_state(
            results,
            round_number,
            "EXTENSION"
        )


        if (
            normal_1 is None
            or flexion is None
            or normal_2 is None
            or extension is None
        ):

            continue


        # ==================================================
        # Median values
        # ==================================================

        n1_pitch = (
            normal_1[
                "summary"
            ][
                "pitch"
            ][
                "median"
            ]
        )


        n2_pitch = (
            normal_2[
                "summary"
            ][
                "pitch"
            ][
                "median"
            ]
        )


        flex_pitch = (
            flexion[
                "summary"
            ][
                "pitch"
            ][
                "median"
            ]
        )


        ext_pitch = (
            extension[
                "summary"
            ][
                "pitch"
            ][
                "median"
            ]
        )


        # ==================================================
        # Normal Reference
        #
        # ใช้ median ของ Normal 1 / Normal 2
        #
        # ตรงนี้เป็น reference สำหรับการทดลองเท่านั้น
        # ยังไม่ใช่ Personal Baseline จริง
        # ==================================================

        normal_pitch = float(
            np.median(
                [
                    n1_pitch,
                    n2_pitch
                ]
            )
        )


        # ==================================================
        # Pitch Delta
        # ==================================================

        flexion_delta = (
            flex_pitch
            - normal_pitch
        )


        extension_delta = (
            ext_pitch
            - normal_pitch
        )


        # ==================================================
        # Normal Return Error
        #
        # ดูว่า Normal 2 กลับมาใกล้ Normal 1 แค่ไหน
        #
        # ตอนนี้ยังไม่ตั้ง Threshold
        # ==================================================

        normal_return_error = abs(
            n2_pitch
            - n1_pitch
        )


        # ==================================================
        # Yaw / Roll Diagnostic
        # ==================================================

        n1_yaw = (
            normal_1[
                "summary"
            ][
                "yaw"
            ][
                "median"
            ]
        )


        n2_yaw = (
            normal_2[
                "summary"
            ][
                "yaw"
            ][
                "median"
            ]
        )


        normal_yaw = float(
            np.median(
                [
                    n1_yaw,
                    n2_yaw
                ]
            )
        )


        n1_roll = (
            normal_1[
                "summary"
            ][
                "roll"
            ][
                "median"
            ]
        )


        n2_roll = (
            normal_2[
                "summary"
            ][
                "roll"
            ][
                "median"
            ]
        )


        normal_roll = float(
            np.median(
                [
                    n1_roll,
                    n2_roll
                ]
            )
        )


        flex_yaw = (
            flexion[
                "summary"
            ][
                "yaw"
            ][
                "median"
            ]
        )


        ext_yaw = (
            extension[
                "summary"
            ][
                "yaw"
            ][
                "median"
            ]
        )


        flex_roll = (
            flexion[
                "summary"
            ][
                "roll"
            ][
                "median"
            ]
        )


        ext_roll = (
            extension[
                "summary"
            ][
                "roll"
            ][
                "median"
            ]
        )


        flex_yaw_delta = (
            flex_yaw
            - normal_yaw
        )


        flex_roll_delta = (
            flex_roll
            - normal_roll
        )


        ext_yaw_delta = (
            ext_yaw
            - normal_yaw
        )


        ext_roll_delta = (
            ext_roll
            - normal_roll
        )


        # ==================================================
        # Direction Check
        #
        # จาก Experiment แรกของระบบเรา:
        #
        # Flexion   → Pitch เพิ่ม
        # Extension → Pitch ลด
        #
        # ตอนนี้เป็น Prototype Convention ที่เราพิสูจน์แล้ว
        # ==================================================

        direction_ok = (
            flexion_delta > 0
            and extension_delta < 0
        )


        # ==================================================
        # Pitch Dominance
        #
        # ตอนก้ม/เงย Pitch ควรเปลี่ยนเด่นกว่า
        # Yaw และ Roll
        #
        # ไม่ใช่ Risk Threshold
        # ==================================================

        flexion_pitch_dominant = (
            abs(
                flexion_delta
            )
            >
            max(
                abs(
                    flex_yaw_delta
                ),
                abs(
                    flex_roll_delta
                )
            )
        )


        extension_pitch_dominant = (
            abs(
                extension_delta
            )
            >
            max(
                abs(
                    ext_yaw_delta
                ),
                abs(
                    ext_roll_delta
                )
            )
        )


        round_reports.append(
            {

                "round": round_number,

                "normal_pitch": normal_pitch,

                "normal_1_pitch": n1_pitch,

                "normal_2_pitch": n2_pitch,

                "normal_return_error": (
                    normal_return_error
                ),

                "flexion_pitch": flex_pitch,

                "flexion_delta": flexion_delta,

                "extension_pitch": ext_pitch,

                "extension_delta": extension_delta,

                "direction_ok": direction_ok,

                "flexion_pitch_dominant": (
                    flexion_pitch_dominant
                ),

                "extension_pitch_dominant": (
                    extension_pitch_dominant
                ),
            }
        )


    return round_reports


# ==========================================================
# Print Final Repeatability Report
# ==========================================================

def print_final_report(
    results
):

    reports = analyse_repeatability(
        results
    )


    print(
        "\n\n"
        "################################################"
    )

    print(
        "POSTGUARD FACE PITCH REPEATABILITY REPORT"
    )

    print(
        "################################################"
    )


    direction_pass_count = 0

    pitch_dominance_pass_count = 0


    for report in reports:

        print(
            f"\nROUND {report['round']}"
        )

        print(
            "----------------------------------------"
        )


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
            f"{report['normal_pitch']:+.3f} deg"
        )


        print(
            "Normal Return Error:",
            f"{report['normal_return_error']:.3f} deg"
        )


        print(
            "Flexion:",
            f"{report['flexion_pitch']:+.3f} deg"
        )


        print(
            "Flexion Delta:",
            f"{report['flexion_delta']:+.3f} deg"
        )


        print(
            "Extension:",
            f"{report['extension_pitch']:+.3f} deg"
        )


        print(
            "Extension Delta:",
            f"{report['extension_delta']:+.3f} deg"
        )


        print(
            "Direction:",
            (
                "PASS"
                if report["direction_ok"]
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


        if report[
            "direction_ok"
        ]:

            direction_pass_count += 1


        if (
            report[
                "flexion_pitch_dominant"
            ]
            and report[
                "extension_pitch_dominant"
            ]
        ):

            pitch_dominance_pass_count += 1


    print(
        "\n"
        "================================================"
    )


    print(
        "Direction Consistency:",
        f"{direction_pass_count}/3"
    )


    print(
        "Pitch Dominance:",
        f"{pitch_dominance_pass_count}/3"
    )


    # ======================================================
    # Prototype Repeatability Result
    #
    # เราต้องการ Direction ถูกครบ 3 รอบ
    # และ Pitch เป็นแกนหลักครบ 3 รอบ
    #
    # ไม่มี Risk Threshold อยู่ตรงนี้
    # ======================================================

    prototype_pass = (
        direction_pass_count == 3
        and pitch_dominance_pass_count == 3
    )


    if prototype_pass:

        print(
            "\n"
            "PROTOTYPE REPEATABILITY: PASS"
        )


        print(
            "Face Pitch consistently separates "
            "Flexion and Extension in this test."
        )


    else:

        print(
            "\n"
            "PROTOTYPE REPEATABILITY: NEEDS REVIEW"
        )


    print(
        "================================================"
    )


    return prototype_pass


# ==========================================================
# Save Results to CSV
# ==========================================================

def save_results_to_csv(
    results
):

    # ======================================================
    # Results Folder
    # ======================================================

    results_dir = (
        BASE_DIR
        / "mediapipe_detection"
        / "tests"
        / "results"
    )


    results_dir.mkdir(
        parents=True,
        exist_ok=True
    )


    # ======================================================
    # Timestamp File Name
    # ======================================================

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    output_path = (
        results_dir
        / (
            "face_pitch_repeatability_"
            + timestamp
            + ".csv"
        )
    )


    # ======================================================
    # CSV
    # ======================================================

    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

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


        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )


        writer.writeheader()


        for result in results:

            summary = (
                result["summary"]
            )


            writer.writerow(
                {

                    "round": (
                        result["round"]
                    ),

                    "state": (
                        result["state"]
                    ),

                    "samples": (
                        summary["samples"]
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

                    "pitch_min": (
                        summary[
                            "pitch"
                        ][
                            "min"
                        ]
                    ),

                    "pitch_max": (
                        summary[
                            "pitch"
                        ][
                            "max"
                        ]
                    ),

                    "yaw_median": (
                        summary[
                            "yaw"
                        ][
                            "median"
                        ]
                    ),

                    "yaw_mean": (
                        summary[
                            "yaw"
                        ][
                            "mean"
                        ]
                    ),

                    "yaw_std": (
                        summary[
                            "yaw"
                        ][
                            "std"
                        ]
                    ),

                    "roll_median": (
                        summary[
                            "roll"
                        ][
                            "median"
                        ]
                    ),

                    "roll_mean": (
                        summary[
                            "roll"
                        ][
                            "mean"
                        ]
                    ),

                    "roll_std": (
                        summary[
                            "roll"
                        ][
                            "std"
                        ]
                    ),
                }
            )


    print(
        "\nResults saved:"
    )

    print(
        output_path
    )


    return output_path


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # 1. Model Check
    # ======================================================

    if not MODEL_PATH.exists():

        print(
            "Error: Face model not found"
        )

        print(
            MODEL_PATH
        )

        return


    # ======================================================
    # 2. Face Detector
    # ======================================================

    face_detector = FaceDetector(
        MODEL_PATH
    )


    # ======================================================
    # 3. Webcam
    # ======================================================

    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        print(
            "Error: Can't open camera"
        )

        face_detector.close()

        return


    # ======================================================
    # 4. Camera Resolution
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
    # 5. Repeatability State
    # ======================================================

    test_index = 0

    results = []


    collecting = False

    collection_start_time = None

    current_samples = []


    status_message = (
        "Press SPACE to capture current state"
    )


    test_complete = False

    results_saved = False


    # ======================================================
    # 6. Main Loop
    # ======================================================

    while True:

        ret, raw_frame = (
            cap.read()
        )


        if not ret:

            print(
                "Error: Can't read frame"
            )

            break


        # ==================================================
        # 7. Frame Size
        # ==================================================

        frame_height, frame_width = (
            raw_frame.shape[:2]
        )


        # ==================================================
        # 8. Face Detection
        # ==================================================

        result = (
            face_detector.detect(
                raw_frame
            )
        )


        # ==================================================
        # 9. Face Points
        # ==================================================

        face_points = (
            extract_face_points(
                result,
                frame_width,
                frame_height
            )
        )


        # ==================================================
        # 10. Validators
        # ==================================================

        head_validation = (
            validate_head_orientation(
                face_points
            )
        )


        eye_validation = (
            validate_eye_points(
                face_points
            )
        )


        # ==================================================
        # 11. Orientation
        # ==================================================

        orientation = (
            extract_face_orientation(
                result
            )
        )


        orientation_valid = (
            orientation is not None
            and head_validation["valid"]
        )


        # ==================================================
        # 12. Repeatability Capture
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                - collection_start_time
            )


            # ----------------------------------------------
            # เก็บเฉพาะ Frame ที่ Orientation Valid
            # ----------------------------------------------

            if orientation_valid:

                current_samples.append(
                    {

                        "pitch": (
                            orientation[
                                "pitch"
                            ]
                        ),

                        "yaw": (
                            orientation[
                                "yaw"
                            ]
                        ),

                        "roll": (
                            orientation[
                                "roll"
                            ]
                        ),
                    }
                )


            # ----------------------------------------------
            # Capture ครบเวลา
            # ----------------------------------------------

            if (
                elapsed
                >= SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ------------------------------------------
                # Valid Samples ไม่พอ
                # → ไม่เลื่อนไป State ต่อไป
                # ------------------------------------------

                if (
                    len(
                        current_samples
                    )
                    <
                    MIN_VALID_SAMPLES
                ):

                    status_message = (
                        "RETRY: not enough valid samples "
                        f"({len(current_samples)})"
                    )


                    print(
                        "\nCapture failed:"
                    )


                    print(
                        "Valid samples:",
                        len(
                            current_samples
                        )
                    )


                    print(
                        "Please repeat current state."
                    )


                    current_samples = []


                # ------------------------------------------
                # Capture ผ่าน
                # ------------------------------------------

                else:

                    step = (
                        TEST_SEQUENCE[
                            test_index
                        ]
                    )


                    summary = (
                        summarize_samples(
                            current_samples
                        )
                    )


                    record = {

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


                    results.append(
                        record
                    )


                    print_state_result(
                        step,
                        summary
                    )


                    # --------------------------------------
                    # Move to Next State
                    # --------------------------------------

                    test_index += 1

                    current_samples = []


                    # --------------------------------------
                    # Test Complete
                    # --------------------------------------

                    if (
                        test_index
                        >= len(
                            TEST_SEQUENCE
                        )
                    ):

                        test_complete = True


                        status_message = (
                            "TEST COMPLETE"
                        )


                        prototype_pass = (
                            print_final_report(
                                results
                            )
                        )


                        if not results_saved:

                            save_results_to_csv(
                                results
                            )

                            results_saved = True


                    # --------------------------------------
                    # Next State
                    # --------------------------------------

                    else:

                        next_step = (
                            TEST_SEQUENCE[
                                test_index
                            ]
                        )


                        status_message = (
                            "Next: "
                            f"Round {next_step['round']} "
                            f"{next_step['state']}"
                        )


        # ==================================================
        # 13. Mirror Display
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # 14. Draw Face Points
        # ==================================================

        display_frame = (
            draw_face_points(
                display_frame,
                face_points,
                mirrored=True
            )
        )


        # ==================================================
        # 15. Face Status
        # ==================================================

        face_found = (
            result is not None
            and bool(
                result.face_landmarks
            )
        )


        if face_found:

            cv2.putText(
                display_frame,
                "Face: OK",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 255, 0),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Face: NOT FOUND",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 0, 255),
                2
            )


        # ==================================================
        # 16. Validator
        # ==================================================

        if head_validation[
            "valid"
        ]:

            validator_text = (
                "Head Validator: VALID"
            )

            validator_color = (
                0,
                255,
                0
            )


        else:

            validator_text = (
                "Head Validator: INVALID"
            )

            validator_color = (
                0,
                0,
                255
            )


        cv2.putText(
            display_frame,
            validator_text,
            (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            validator_color,
            2
        )


        # ==================================================
        # 17. Orientation
        # ==================================================

        if orientation_valid:

            cv2.putText(
                display_frame,
                (
                    "Pitch: "
                    f"{orientation['pitch']:+.2f}"
                ),
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Yaw: "
                    f"{orientation['yaw']:+.2f}"
                ),
                (20, 135),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Roll: "
                    f"{orientation['roll']:+.2f}"
                ),
                (20, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Orientation: INVALID",
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # 18. Current Repeatability State
        # ==================================================

        if not test_complete:

            current_step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


            current_text = (
                f"Round {current_step['round']}/3  "
                f"State: {current_step['state']}"
            )


        else:

            current_text = (
                "Repeatability Test Complete"
            )


        cv2.putText(
            display_frame,
            current_text,
            (20, 210),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (0, 255, 255),
            2
        )


        # ==================================================
        # 19. Capture Progress
        # ==================================================

        if collecting:

            elapsed = min(
                time.perf_counter()
                - collection_start_time,
                SAMPLE_DURATION_SECONDS
            )


            progress_text = (
                "CAPTURING "
                f"{elapsed:.1f}/"
                f"{SAMPLE_DURATION_SECONDS:.1f}s "
                f"samples={len(current_samples)}"
            )


            progress_color = (
                0,
                255,
                255
            )


        else:

            progress_text = (
                status_message
            )


            progress_color = (
                255,
                255,
                255
            )


        cv2.putText(
            display_frame,
            progress_text,
            (20, 245),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            progress_color,
            2
        )


        # ==================================================
        # 20. Instructions
        # ==================================================

        cv2.putText(
            display_frame,
            "SPACE=Capture 2s   P=Print   R=Reset   Q=Quit",
            (
                20,
                frame_height - 30
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.47,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )


        # ==================================================
        # 21. Display
        # ==================================================

        cv2.imshow(
            "PostGuard - Face Pitch Repeatability",
            display_frame
        )


        # ==================================================
        # 22. Keyboard
        # ==================================================

        key = (
            cv2.waitKey(1)
            & 0xFF
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
        # SPACE
        #
        # Start Current State Capture
        # ==================================================

        if (
            key == ord(" ")
            and not collecting
            and not test_complete
        ):

            if not orientation_valid:

                print(
                    "Cannot capture:"
                    " orientation is INVALID"
                )


                status_message = (
                    "Cannot capture: orientation INVALID"
                )


            else:

                step = (
                    TEST_SEQUENCE[
                        test_index
                    ]
                )


                print(
                    "\nStart capture:"
                )


                print(
                    "Round:",
                    step["round"]
                )


                print(
                    "State:",
                    step["state"]
                )


                collecting = True

                collection_start_time = (
                    time.perf_counter()
                )

                current_samples = []


        # ==================================================
        # P
        #
        # Print Current Orientation
        # ==================================================

        if (
            key in (
                ord("p"),
                ord("P")
            )
            and orientation_valid
        ):

            print(
                "\nCURRENT ORIENTATION"
            )


            print(
                "Pitch:",
                f"{orientation['pitch']:+.3f}"
            )


            print(
                "Yaw:",
                f"{orientation['yaw']:+.3f}"
            )


            print(
                "Roll:",
                f"{orientation['roll']:+.3f}"
            )


        # ==================================================
        # R
        #
        # Reset Entire Repeatability Test
        # ==================================================

        if key in (
            ord("r"),
            ord("R")
        ):

            test_index = 0

            results = []

            collecting = False

            current_samples = []

            test_complete = False

            results_saved = False


            status_message = (
                "Test reset - start Round 1 NORMAL_1"
            )


            print(
                "\nRepeatability test RESET"
            )


    # ======================================================
    # 23. Cleanup
    # ======================================================

    cap.release()

    face_detector.close()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    main()