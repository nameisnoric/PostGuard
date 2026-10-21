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

from mediapipe_detection.face.face_validator import (
    validate_head_orientation
)

from mediapipe_detection.face.face_orientation import (
    extract_face_orientation
)


# ==========================================================
# Pose
# ==========================================================

from mediapipe_detection.pose.pose_detector import (
    PoseDetector
)


# ==========================================================
# Torso Orientation
# ==========================================================

from mediapipe_detection.posture.torso_orientation import (
    calculate_torso_orientation
)


# ==========================================================
# Relative Neck Rotation
# ==========================================================

from mediapipe_detection.posture.relative_neck_rotation import (
    calculate_relative_neck_rotation,
    TORSO_MAPPING_K,
)


# ==========================================================
# Models
# ==========================================================

FACE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "face_landmarker.task"
)


POSE_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "pose_landmarker_lite.task"
)


# ==========================================================
# Capture Settings
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# FINAL TEST SEQUENCE
#
# Normal ก่อนแต่ละ Test State
# จะถูกใช้เป็น local experimental reference
#
# ยังไม่ใช่ Personal Baseline จริง
# ==========================================================

TEST_SEQUENCE = [

    {
        "state": "NORMAL_1",
        "type": "NORMAL",
        "baseline": None,
    },

    {
        "state": "HEAD_LEFT",
        "type": "TEST",
        "baseline": "NORMAL_1",
    },

    {
        "state": "NORMAL_2",
        "type": "NORMAL",
        "baseline": None,
    },

    {
        "state": "BODY_LEFT",
        "type": "TEST",
        "baseline": "NORMAL_2",
    },

    {
        "state": "NORMAL_3",
        "type": "NORMAL",
        "baseline": None,
    },

    {
        "state": "HEAD_RIGHT",
        "type": "TEST",
        "baseline": "NORMAL_3",
    },

    {
        "state": "NORMAL_4",
        "type": "NORMAL",
        "baseline": None,
    },

    {
        "state": "BODY_RIGHT",
        "type": "TEST",
        "baseline": "NORMAL_4",
    },
]


# ==========================================================
# Statistics
# ==========================================================

def summarize_axis(values):

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


def summarize_samples(samples):

    face_yaw_values = [
        sample["face_yaw"]
        for sample in samples
    ]


    torso_values = [
        sample["torso_angle"]
        for sample in samples
    ]


    return {

        "samples": len(samples),

        "face_yaw": summarize_axis(
            face_yaw_values
        ),

        "torso": summarize_axis(
            torso_values
        ),
    }


# ==========================================================
# Relative Summary
# ==========================================================

def summarize_relative_samples(
    samples,
    head_baseline,
    torso_baseline
):

    head_deltas = []

    torso_deltas = []

    torso_equivalents = []

    relative_values = []


    for sample in samples:

        relative = (
            calculate_relative_neck_rotation(

                head_yaw=(
                    sample[
                        "face_yaw"
                    ]
                ),

                torso_angle=(
                    sample[
                        "torso_angle"
                    ]
                ),

                head_baseline=(
                    head_baseline
                ),

                torso_baseline=(
                    torso_baseline
                ),
            )
        )


        if relative is None:
            continue


        head_deltas.append(
            relative[
                "head_delta"
            ]
        )


        torso_deltas.append(
            relative[
                "torso_delta"
            ]
        )


        torso_equivalents.append(
            relative[
                "torso_equivalent"
            ]
        )


        relative_values.append(
            relative[
                "relative_neck_rotation"
            ]
        )


    if not relative_values:
        return None


    return {

        "samples": len(
            relative_values
        ),

        "head_delta": summarize_axis(
            head_deltas
        ),

        "torso_delta": summarize_axis(
            torso_deltas
        ),

        "torso_equivalent": summarize_axis(
            torso_equivalents
        ),

        "relative_neck": summarize_axis(
            relative_values
        ),
    }


# ==========================================================
# Get Stored Result
# ==========================================================

def get_result_by_state(
    results,
    state
):

    for result in results:

        if (
            result[
                "state"
            ]
            ==
            state
        ):
            return result


    return None


# ==========================================================
# Print Normal State
# ==========================================================

def print_normal_result(
    state,
    summary
):

    print(
        "\n"
        "========================================"
    )


    print(
        "STATE:",
        state
    )


    print(
        "TYPE: NORMAL REFERENCE"
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
        "Face Yaw Median:",
        f"{summary['face_yaw']['median']:+.3f} deg"
    )


    print(
        "Torso Angle Median:",
        f"{summary['torso']['median']:+.3f} deg"
    )


    print(
        "========================================"
    )


# ==========================================================
# Print Test State
# ==========================================================

def print_test_result(
    state,
    baseline_name,
    summary,
    relative_summary
):

    print(
        "\n"
        "========================================"
    )


    print(
        "STATE:",
        state
    )


    print(
        "BASELINE:",
        baseline_name
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
        "Face Yaw Median:",
        f"{summary['face_yaw']['median']:+.3f} deg"
    )


    print(
        "Torso Angle Median:",
        f"{summary['torso']['median']:+.3f} deg"
    )


    print(
        "----------------------------------------"
    )


    print(
        "Head Delta"
    )


    print(
        "  Median:",
        f"{relative_summary['head_delta']['median']:+.3f} deg"
    )


    print(
        "  Mean  :",
        f"{relative_summary['head_delta']['mean']:+.3f} deg"
    )


    print(
        "  Std   :",
        f"{relative_summary['head_delta']['std']:.3f} deg"
    )


    print(
        "Torso Delta"
    )


    print(
        "  Median:",
        f"{relative_summary['torso_delta']['median']:+.3f} deg"
    )


    print(
        "Torso Equivalent"
    )


    print(
        "  Median:",
        f"{relative_summary['torso_equivalent']['median']:+.3f} deg"
    )


    print(
        "RELATIVE NECK ROTATION"
    )


    print(
        "  Median:",
        f"{relative_summary['relative_neck']['median']:+.3f} deg"
    )


    print(
        "  Mean  :",
        f"{relative_summary['relative_neck']['mean']:+.3f} deg"
    )


    print(
        "  Std   :",
        f"{relative_summary['relative_neck']['std']:.3f} deg"
    )


    print(
        "========================================"
    )


# ==========================================================
# FINAL VALIDATION
# ==========================================================

def print_final_report(results):

    head_left = get_result_by_state(
        results,
        "HEAD_LEFT"
    )


    body_left = get_result_by_state(
        results,
        "BODY_LEFT"
    )


    head_right = get_result_by_state(
        results,
        "HEAD_RIGHT"
    )


    body_right = get_result_by_state(
        results,
        "BODY_RIGHT"
    )


    if any(
        result is None
        for result in (
            head_left,
            body_left,
            head_right,
            body_right,
        )
    ):

        print(
            "ERROR: Final test incomplete."
        )

        return False


    hl = (
        head_left[
            "relative"
        ][
            "relative_neck"
        ][
            "median"
        ]
    )


    bl = (
        body_left[
            "relative"
        ][
            "relative_neck"
        ][
            "median"
        ]
    )


    hr = (
        head_right[
            "relative"
        ][
            "relative_neck"
        ][
            "median"
        ]
    )


    br = (
        body_right[
            "relative"
        ][
            "relative_neck"
        ][
            "median"
        ]
    )


    # ======================================================
    # Behaviour Checks
    #
    # ไม่มี Risk Threshold
    #
    # เราตรวจแค่:
    #
    # 1. Head Left / Right คนละทิศ
    # 2. Whole-body rotation ถูก suppress
    #
    # ======================================================

    opposite_head_direction = (
        hl * hr < 0
    )


    left_body_suppressed = (
        abs(bl)
        <
        abs(hl)
    )


    right_body_suppressed = (
        abs(br)
        <
        abs(hr)
    )


    # ======================================================
    # Suppression Ratio
    #
    # ยิ่งต่ำ = ยิ่งดี
    #
    # ไม่ใช้เป็น risk threshold
    # ======================================================

    left_suppression_ratio = (
        abs(bl)
        /
        abs(hl)
        if abs(hl) > 1e-6
        else None
    )


    right_suppression_ratio = (
        abs(br)
        /
        abs(hr)
        if abs(hr) > 1e-6
        else None
    )


    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD FINAL RELATIVE NECK ROTATION TEST"
    )


    print(
        "################################################"
    )


    print(
        "\nMapping k:"
    )


    print(
        f"{TORSO_MAPPING_K:+.4f}"
    )


    print(
        "\nHEAD_LEFT"
    )


    print(
        "Relative Neck:",
        f"{hl:+.3f} deg"
    )


    print(
        "\nBODY_LEFT"
    )


    print(
        "Relative Neck:",
        f"{bl:+.3f} deg"
    )


    print(
        "\nHEAD_RIGHT"
    )


    print(
        "Relative Neck:",
        f"{hr:+.3f} deg"
    )


    print(
        "\nBODY_RIGHT"
    )


    print(
        "Relative Neck:",
        f"{br:+.3f} deg"
    )


    print(
        "\n"
        "================================================"
    )


    print(
        "Head LEFT/RIGHT Opposite Direction:",
        (
            "PASS"
            if opposite_head_direction
            else "FAIL"
        )
    )


    print(
        "BODY_LEFT Suppressed:",
        (
            "PASS"
            if left_body_suppressed
            else "FAIL"
        )
    )


    print(
        "BODY_RIGHT Suppressed:",
        (
            "PASS"
            if right_body_suppressed
            else "FAIL"
        )
    )


    if (
        left_suppression_ratio
        is not None
    ):

        print(
            "LEFT Suppression Ratio:",
            f"{left_suppression_ratio:.3f}"
        )


    if (
        right_suppression_ratio
        is not None
    ):

        print(
            "RIGHT Suppression Ratio:",
            f"{right_suppression_ratio:.3f}"
        )


    # ======================================================
    # Final Prototype Result
    # ======================================================

    final_pass = (

        opposite_head_direction

        and
        left_body_suppressed

        and
        right_body_suppressed
    )


    print(
        "\n"
        "------------------------------------------------"
    )


    if final_pass:

        print(
            "FINAL RELATIVE NECK ROTATION: PASS"
        )


        print(
            "Head-only rotation remains strong, "
            "while whole-body rotation is reduced."
        )


        print(
            "\nNeck Rotation can be LOCKED "
            "as a Validated Prototype Metric."
        )


    else:

        print(
            "FINAL RELATIVE NECK ROTATION: NEEDS REVIEW"
        )


        print(
            "Do not lock Neck Rotation yet."
        )


    print(
        "================================================"
    )


    return final_pass


# ==========================================================
# Save CSV
# ==========================================================

def save_results(results):

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


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    output_path = (
        output_dir
        /
        (
            "final_relative_neck_rotation_"
            + timestamp
            + ".csv"
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
                "state",
                "baseline",
                "samples",

                "face_yaw_median",
                "face_yaw_mean",
                "face_yaw_std",

                "torso_angle_median",
                "torso_angle_mean",
                "torso_angle_std",

                "head_delta_median",
                "torso_delta_median",
                "torso_equivalent_median",

                "relative_neck_median",
                "relative_neck_mean",
                "relative_neck_std",
            ]
        )


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            relative = (
                result.get(
                    "relative"
                )
            )


            writer.writerow(
                [
                    result[
                        "state"
                    ],

                    result.get(
                        "baseline",
                        ""
                    ),

                    summary[
                        "samples"
                    ],

                    summary[
                        "face_yaw"
                    ][
                        "median"
                    ],

                    summary[
                        "face_yaw"
                    ][
                        "mean"
                    ],

                    summary[
                        "face_yaw"
                    ][
                        "std"
                    ],

                    summary[
                        "torso"
                    ][
                        "median"
                    ],

                    summary[
                        "torso"
                    ][
                        "mean"
                    ],

                    summary[
                        "torso"
                    ][
                        "std"
                    ],

                    (
                        relative[
                            "head_delta"
                        ][
                            "median"
                        ]
                        if relative
                        else ""
                    ),

                    (
                        relative[
                            "torso_delta"
                        ][
                            "median"
                        ]
                        if relative
                        else ""
                    ),

                    (
                        relative[
                            "torso_equivalent"
                        ][
                            "median"
                        ]
                        if relative
                        else ""
                    ),

                    (
                        relative[
                            "relative_neck"
                        ][
                            "median"
                        ]
                        if relative
                        else ""
                    ),

                    (
                        relative[
                            "relative_neck"
                        ][
                            "mean"
                        ]
                        if relative
                        else ""
                    ),

                    (
                        relative[
                            "relative_neck"
                        ][
                            "std"
                        ]
                        if relative
                        else ""
                    ),
                ]
            )


    print(
        "\nResults saved:"
    )


    print(
        output_path
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    # ======================================================
    # Models
    # ======================================================

    if not FACE_MODEL_PATH.exists():

        print(
            "Face model not found:"
        )

        print(
            FACE_MODEL_PATH
        )

        return


    if not POSE_MODEL_PATH.exists():

        print(
            "Pose model not found:"
        )

        print(
            POSE_MODEL_PATH
        )

        return


    # ======================================================
    # Detectors
    # ======================================================

    face_detector = FaceDetector(
        FACE_MODEL_PATH
    )


    pose_detector = PoseDetector(
        POSE_MODEL_PATH
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
    # Main Loop
    # ======================================================

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
        # FACE
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


        face_validation = (
            validate_head_orientation(
                face_points
            )
        )


        orientation = (
            extract_face_orientation(
                face_result
            )
        )


        # ==================================================
        # POSE
        # ==================================================

        pose_points = (
            pose_detector.detect(
                raw_frame
            )
        )


        torso = (
            calculate_torso_orientation(
                pose_points
            )
        )


        # ==================================================
        # Validity
        # ==================================================

        face_valid = (

            orientation is not None

            and
            face_validation[
                "valid"
            ]
        )


        torso_valid = (
            torso is not None
        )


        sample_valid = (
            face_valid
            and
            torso_valid
        )


        # ==================================================
        # Current test definition
        # ==================================================

        current_step = None


        if not test_complete:

            current_step = (
                TEST_SEQUENCE[
                    test_index
                ]
            )


        # ==================================================
        # LIVE RELATIVE VALUE
        #
        # แสดงได้เฉพาะ TEST state
        # ที่ Normal baseline ถูก capture ไปแล้ว
        # ==================================================

        live_relative = None


        if (
            current_step is not None
            and
            current_step[
                "type"
            ]
            ==
            "TEST"
            and
            sample_valid
        ):

            baseline_record = (
                get_result_by_state(
                    results,
                    current_step[
                        "baseline"
                    ]
                )
            )


            if baseline_record is not None:

                head_baseline = (
                    baseline_record[
                        "summary"
                    ][
                        "face_yaw"
                    ][
                        "median"
                    ]
                )


                torso_baseline = (
                    baseline_record[
                        "summary"
                    ][
                        "torso"
                    ][
                        "median"
                    ]
                )


                live_relative = (
                    calculate_relative_neck_rotation(

                        head_yaw=(
                            orientation[
                                "yaw"
                            ]
                        ),

                        torso_angle=(
                            torso[
                                "angle"
                            ]
                        ),

                        head_baseline=(
                            head_baseline
                        ),

                        torso_baseline=(
                            torso_baseline
                        ),
                    )
                )


        # ==================================================
        # CAPTURE
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                -
                collection_start
            )


            if sample_valid:

                samples.append(
                    {

                        "face_yaw": (
                            orientation[
                                "yaw"
                            ]
                        ),

                        "torso_angle": (
                            torso[
                                "angle"
                            ]
                        ),
                    }
                )


            if (
                elapsed
                >=
                SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ==========================================
                # Not enough valid samples
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


                    status_message = (
                        "RETRY CURRENT STATE"
                    )


                    samples = []


                # ==========================================
                # Successful capture
                # ==========================================

                else:

                    step = (
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

                        "state": (
                            step[
                                "state"
                            ]
                        ),

                        "type": (
                            step[
                                "type"
                            ]
                        ),

                        "baseline": (
                            step[
                                "baseline"
                            ]
                        ),

                        "summary": (
                            summary
                        ),

                        "relative": None,
                    }


                    # ======================================
                    # NORMAL
                    # ======================================

                    if (
                        step[
                            "type"
                        ]
                        ==
                        "NORMAL"
                    ):

                        print_normal_result(
                            step[
                                "state"
                            ],
                            summary
                        )


                    # ======================================
                    # TEST state
                    # ======================================

                    else:

                        baseline_record = (
                            get_result_by_state(
                                results,
                                step[
                                    "baseline"
                                ]
                            )
                        )


                        if baseline_record is None:

                            print(
                                "ERROR: baseline missing."
                            )

                            break


                        head_baseline = (
                            baseline_record[
                                "summary"
                            ][
                                "face_yaw"
                            ][
                                "median"
                            ]
                        )


                        torso_baseline = (
                            baseline_record[
                                "summary"
                            ][
                                "torso"
                            ][
                                "median"
                            ]
                        )


                        relative_summary = (
                            summarize_relative_samples(

                                samples=(
                                    samples
                                ),

                                head_baseline=(
                                    head_baseline
                                ),

                                torso_baseline=(
                                    torso_baseline
                                ),
                            )
                        )


                        record[
                            "relative"
                        ] = (
                            relative_summary
                        )


                        print_test_result(

                            state=(
                                step[
                                    "state"
                                ]
                            ),

                            baseline_name=(
                                step[
                                    "baseline"
                                ]
                            ),

                            summary=(
                                summary
                            ),

                            relative_summary=(
                                relative_summary
                            ),
                        )


                    # ======================================
                    # Store
                    # ======================================

                    results.append(
                        record
                    )


                    samples = []

                    test_index += 1


                    # ======================================
                    # Complete
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
                                "FINAL TEST PASS"
                            )


                        else:

                            status_message = (
                                "FINAL TEST NEEDS REVIEW"
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
        # DISPLAY
        #
        # Mirror display only
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # Face
        # ==================================================

        if face_valid:

            cv2.putText(
                display_frame,
                (
                    "Face Yaw: "
                    f"{orientation['yaw']:+.2f} deg"
                ),
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Face: INVALID",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Torso
        # ==================================================

        if torso_valid:

            cv2.putText(
                display_frame,
                (
                    "Torso Angle: "
                    f"{torso['angle']:+.2f} deg"
                ),
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2
            )


        else:

            cv2.putText(
                display_frame,
                "Torso: INVALID",
                (20, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2
            )


        # ==================================================
        # Relative live
        # ==================================================

        if live_relative is not None:

            cv2.putText(
                display_frame,
                (
                    "Relative Neck: "
                    f"{live_relative['relative_neck_rotation']:+.2f} deg"
                ),
                (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (0, 255, 0),
                2
            )


        # ==================================================
        # State
        # ==================================================

        if not test_complete:

            state_text = (
                f"{test_index + 1}/"
                f"{len(TEST_SEQUENCE)} "
                f"{current_step['state']}"
            )


        else:

            state_text = (
                "FINAL TEST COMPLETE"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 155),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )


        # ==================================================
        # Status
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
            (20, 190),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (255, 255, 255),
            2
        )


        cv2.putText(
            display_frame,
            "SPACE=Capture  R=Reset  Q=Quit",
            (
                20,
                frame_height - 30
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1
        )


        cv2.imshow(
            "PostGuard - Final Relative Neck Rotation",
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
        # SPACE Capture
        # ==================================================

        if (
            key == ord(" ")
            and
            not collecting
            and
            not test_complete
        ):

            if not sample_valid:

                print(
                    "Face / Torso INVALID"
                )


            else:

                print(
                    "\nStart capture:"
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

            results_saved = False


            status_message = (
                "RESET - start NORMAL_1"
            )


            print(
                "\nFinal test RESET"
            )


    # ======================================================
    # Cleanup
    # ======================================================

    cap.release()

    face_detector.close()

    pose_detector.close()

    cv2.destroyAllWindows()


if __name__ == "__main__":

    main()