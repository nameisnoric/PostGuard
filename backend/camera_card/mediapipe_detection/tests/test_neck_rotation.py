from pathlib import Path
import sys
import time
import csv
import math
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
# Add camera_card to Python path
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
    validate_head_orientation
)

from mediapipe_detection.face.face_orientation import (
    extract_face_orientation
)


# ==========================================================
# Pose Modules
# ==========================================================

from mediapipe_detection.pose.pose_detector import (
    PoseDetector
)


# ==========================================================
# Model Paths
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
# Test Settings
# ==========================================================

SAMPLE_DURATION_SECONDS = 2.0

MIN_VALID_SAMPLES = 15


# ==========================================================
# Disturbance Experiment
#
# ไม่ทำ 3 รอบแล้ว
#
# เพราะ Face Yaw repeatability ผ่านแล้ว
#
# รอบนี้ต้องการพิสูจน์ว่า:
#
# HEAD_LEFT
# = หัวหมุน แต่ torso ไม่หมุน
#
# BODY_LEFT
# = หัวและ torso หมุนพร้อมกัน
# ==========================================================

TEST_SEQUENCE = [

    {
        "state": "NORMAL_1",
    },

    {
        "state": "HEAD_LEFT",
    },

    {
        "state": "NORMAL_2",
    },

    {
        "state": "BODY_LEFT",
    },
]


# ==========================================================
# Finite Number Check
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
# Shoulder / Torso Rotation Candidate
#
# ใช้ Pose World Landmarks:
#
# Left Shoulder
# Right Shoulder
#
# ดู shoulder vector ในระนาบ X-Z
#
#
#          Z (depth)
#          ↑
#
# Left -------- Right
#        X
#
#
# ถ้าลำตัวหมุน:
# shoulder depth ของซ้าย/ขวาจะต่างกัน
#
#
# IMPORTANT:
# ตอนนี้เป็น EXPERIMENTAL TORSO SIGNAL
#
# ยังไม่ใช่ production Neck Rotation formula
# ==========================================================

def calculate_shoulder_depth_angle(
    pose_points
):

    # ======================================================
    # 1. Pose ไม่มีข้อมูล
    # ======================================================

    if pose_points is None:

        return None


    # ======================================================
    # 2. ต้องมีไหล่สองข้าง
    # ======================================================

    if (
        "left_shoulder" not in pose_points
        or
        "right_shoulder" not in pose_points
    ):

        return None


    left = (
        pose_points[
            "left_shoulder"
        ]
    )


    right = (
        pose_points[
            "right_shoulder"
        ]
    )


    # ======================================================
    # 3. ต้องมี World Coordinates
    # ======================================================

    required_keys = (
        "world_x",
        "world_y",
        "world_z",
    )


    for key in required_keys:

        if (
            key not in left
            or
            key not in right
        ):

            return None


        if (
            not is_finite_number(
                left[key]
            )
            or
            not is_finite_number(
                right[key]
            )
        ):

            return None


    # ======================================================
    # 4. Shoulder Vector
    #
    # Anatomical:
    #
    # Left Shoulder -> Right Shoulder
    # ======================================================

    dx = (
        right["world_x"]
        -
        left["world_x"]
    )


    dy = (
        right["world_y"]
        -
        left["world_y"]
    )


    dz = (
        right["world_z"]
        -
        left["world_z"]
    )


    # ======================================================
    # 5. Horizontal Shoulder Width
    #
    # เราใช้ abs(dx) เพราะต้องการ denominator
    # เป็นขนาด separation
    #
    # ส่วน direction มาจาก dz
    # ======================================================

    horizontal_width = abs(
        dx
    )


    # ป้องกันหารด้วยค่าที่เกือบ 0
    if horizontal_width < 1e-6:

        return None


    # ======================================================
    # 6. Shoulder Depth Angle
    #
    # ถ้าไหล่ทั้งสองอยู่ depth ใกล้กัน:
    #
    # dz ≈ 0
    # angle ≈ 0°
    #
    # ถ้าหมุน torso:
    #
    # |dz| เพิ่ม
    # |angle| เพิ่ม
    #
    # Sign จะตรวจจากผลจริง
    # ยังไม่ hard-code
    # ======================================================

    depth_angle_rad = math.atan2(
        dz,
        horizontal_width
    )


    depth_angle_deg = math.degrees(
        depth_angle_rad
    )


    # ======================================================
    # 7. Shoulder Width in X-Z Plane
    #
    # ใช้ diagnostic
    # ======================================================

    shoulder_width_xz = math.sqrt(
        (
            dx * dx
        )
        +
        (
            dz * dz
        )
    )


    # ======================================================
    # 8. Full 3D Shoulder Distance
    # ======================================================

    shoulder_width_3d = math.sqrt(
        (
            dx * dx
        )
        +
        (
            dy * dy
        )
        +
        (
            dz * dz
        )
    )


    # ======================================================
    # 9. Return
    # ======================================================

    return {

        "depth_angle": (
            depth_angle_deg
        ),

        "world_dx": (
            float(dx)
        ),

        "world_dy": (
            float(dy)
        ),

        "world_dz": (
            float(dz)
        ),

        "shoulder_width_xz": (
            float(
                shoulder_width_xz
            )
        ),

        "shoulder_width_3d": (
            float(
                shoulder_width_3d
            )
        ),

        # เก็บ quality ไว้ดูด้วย
        "left_visibility": (
            left.get(
                "visibility"
            )
        ),

        "right_visibility": (
            right.get(
                "visibility"
            )
        ),

        "left_presence": (
            left.get(
                "presence"
            )
        ),

        "right_presence": (
            right.get(
                "presence"
            )
        ),
    }


# ==========================================================
# Summary Axis
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
# Summary Samples
# ==========================================================

def summarize_samples(
    samples
):

    yaw_values = [
        sample["yaw"]
        for sample in samples
    ]


    pitch_values = [
        sample["pitch"]
        for sample in samples
    ]


    roll_values = [
        sample["roll"]
        for sample in samples
    ]


    torso_values = [
        sample["torso_depth_angle"]
        for sample in samples
    ]


    return {

        "samples": len(
            samples
        ),

        "yaw": summarize_axis(
            yaw_values
        ),

        "pitch": summarize_axis(
            pitch_values
        ),

        "roll": summarize_axis(
            roll_values
        ),

        "torso": summarize_axis(
            torso_values
        ),
    }


# ==========================================================
# Print State Summary
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


    # ======================================================
    # Face Yaw
    # ======================================================

    print(
        "Face Yaw"
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
    # Torso Candidate
    # ======================================================

    print(
        "Shoulder Depth Angle"
    )


    print(
        "  Median:",
        f"{summary['torso']['median']:+.3f} deg"
    )


    print(
        "  Mean  :",
        f"{summary['torso']['mean']:+.3f} deg"
    )


    print(
        "  Std   :",
        f"{summary['torso']['std']:.3f} deg"
    )


    # ======================================================
    # Face diagnostics
    # ======================================================

    print(
        "Pitch Median:",
        f"{summary['pitch']['median']:+.3f} deg"
    )


    print(
        "Roll Median :",
        f"{summary['roll']['median']:+.3f} deg"
    )


    print(
        "=============================================="
    )


# ==========================================================
# Find Result by State
# ==========================================================

def get_state(
    results,
    state
):

    for result in results:

        if (
            result["state"]
            ==
            state
        ):

            return result


    return None


# ==========================================================
# Analyse Disturbance Experiment
# ==========================================================

def analyse_disturbance(
    results
):

    normal_1 = get_state(
        results,
        "NORMAL_1"
    )


    head_left = get_state(
        results,
        "HEAD_LEFT"
    )


    normal_2 = get_state(
        results,
        "NORMAL_2"
    )


    body_left = get_state(
        results,
        "BODY_LEFT"
    )


    if (
        normal_1 is None
        or
        head_left is None
        or
        normal_2 is None
        or
        body_left is None
    ):

        return None


    # ======================================================
    # Normal Face Yaw Reference
    # ======================================================

    normal_yaw = float(
        np.median(
            [
                normal_1[
                    "summary"
                ][
                    "yaw"
                ][
                    "median"
                ],

                normal_2[
                    "summary"
                ][
                    "yaw"
                ][
                    "median"
                ],
            ]
        )
    )


    # ======================================================
    # Normal Torso Reference
    # ======================================================

    normal_torso = float(
        np.median(
            [
                normal_1[
                    "summary"
                ][
                    "torso"
                ][
                    "median"
                ],

                normal_2[
                    "summary"
                ][
                    "torso"
                ][
                    "median"
                ],
            ]
        )
    )


    # ======================================================
    # HEAD_LEFT
    # ======================================================

    head_yaw = (
        head_left[
            "summary"
        ][
            "yaw"
        ][
            "median"
        ]
    )


    head_torso = (
        head_left[
            "summary"
        ][
            "torso"
        ][
            "median"
        ]
    )


    head_yaw_delta = (
        head_yaw
        -
        normal_yaw
    )


    head_torso_delta = (
        head_torso
        -
        normal_torso
    )


    # ======================================================
    # BODY_LEFT
    # ======================================================

    body_yaw = (
        body_left[
            "summary"
        ][
            "yaw"
        ][
            "median"
        ]
    )


    body_torso = (
        body_left[
            "summary"
        ][
            "torso"
        ][
            "median"
        ]
    )


    body_yaw_delta = (
        body_yaw
        -
        normal_yaw
    )


    body_torso_delta = (
        body_torso
        -
        normal_torso
    )


    # ======================================================
    # Normal Return Error
    # ======================================================

    normal_yaw_return_error = abs(

        normal_2[
            "summary"
        ][
            "yaw"
        ][
            "median"
        ]

        -

        normal_1[
            "summary"
        ][
            "yaw"
        ][
            "median"
        ]
    )


    normal_torso_return_error = abs(

        normal_2[
            "summary"
        ][
            "torso"
        ][
            "median"
        ]

        -

        normal_1[
            "summary"
        ][
            "torso"
        ][
            "median"
        ]
    )


    # ======================================================
    # Pattern Checks
    #
    # ไม่ใช่ clinical/risk thresholds
    #
    # เป็นเพียง comparative experimental checks
    # ======================================================

    # HEAD_LEFT:
    # Face change ควรเด่นกว่า torso change
    head_is_face_dominant = (
        abs(
            head_yaw_delta
        )
        >
        abs(
            head_torso_delta
        )
    )


    # BODY_LEFT:
    # Torso signal ควรเปลี่ยนมากกว่า
    # ตอน HEAD_LEFT
    body_torso_detected = (
        abs(
            body_torso_delta
        )
        >
        abs(
            head_torso_delta
        )
    )


    return {

        "normal_yaw": (
            normal_yaw
        ),

        "normal_torso": (
            normal_torso
        ),

        "head_yaw": (
            head_yaw
        ),

        "head_yaw_delta": (
            head_yaw_delta
        ),

        "head_torso": (
            head_torso
        ),

        "head_torso_delta": (
            head_torso_delta
        ),

        "body_yaw": (
            body_yaw
        ),

        "body_yaw_delta": (
            body_yaw_delta
        ),

        "body_torso": (
            body_torso
        ),

        "body_torso_delta": (
            body_torso_delta
        ),

        "normal_yaw_return_error": (
            normal_yaw_return_error
        ),

        "normal_torso_return_error": (
            normal_torso_return_error
        ),

        "head_is_face_dominant": (
            head_is_face_dominant
        ),

        "body_torso_detected": (
            body_torso_detected
        ),
    }


# ==========================================================
# Final Report
# ==========================================================

def print_final_report(
    results
):

    report = analyse_disturbance(
        results
    )


    print(
        "\n\n"
        "################################################"
    )


    print(
        "POSTGUARD NECK ROTATION DISTURBANCE REPORT"
    )


    print(
        "################################################"
    )


    if report is None:

        print(
            "ERROR: incomplete experiment data"
        )

        return


    print(
        "\nNORMAL REFERENCE"
    )


    print(
        "Face Yaw:",
        f"{report['normal_yaw']:+.3f} deg"
    )


    print(
        "Shoulder Depth Angle:",
        f"{report['normal_torso']:+.3f} deg"
    )


    # ======================================================
    # Head only
    # ======================================================

    print(
        "\nHEAD_LEFT"
    )


    print(
        "Face Yaw:",
        f"{report['head_yaw']:+.3f} deg"
    )


    print(
        "Face Yaw Delta:",
        f"{report['head_yaw_delta']:+.3f} deg"
    )


    print(
        "Shoulder Depth Angle:",
        f"{report['head_torso']:+.3f} deg"
    )


    print(
        "Torso Delta:",
        f"{report['head_torso_delta']:+.3f} deg"
    )


    print(
        "Face dominant:",
        (
            "PASS"
            if report[
                "head_is_face_dominant"
            ]
            else "NEEDS REVIEW"
        )
    )


    # ======================================================
    # Whole body
    # ======================================================

    print(
        "\nBODY_LEFT"
    )


    print(
        "Face Yaw:",
        f"{report['body_yaw']:+.3f} deg"
    )


    print(
        "Face Yaw Delta:",
        f"{report['body_yaw_delta']:+.3f} deg"
    )


    print(
        "Shoulder Depth Angle:",
        f"{report['body_torso']:+.3f} deg"
    )


    print(
        "Torso Delta:",
        f"{report['body_torso_delta']:+.3f} deg"
    )


    print(
        "Torso Rotation Detected:",
        (
            "PASS"
            if report[
                "body_torso_detected"
            ]
            else "NEEDS REVIEW"
        )
    )


    # ======================================================
    # Return
    # ======================================================

    print(
        "\nNORMAL RETURN"
    )


    print(
        "Face Yaw Return Error:",
        f"{report['normal_yaw_return_error']:.3f} deg"
    )


    print(
        "Torso Return Error:",
        f"{report['normal_torso_return_error']:.3f} deg"
    )


    print(
        "\n"
        "================================================"
    )


    # ======================================================
    # Interpretation
    # ======================================================

    if (
        report[
            "head_is_face_dominant"
        ]
        and
        report[
            "body_torso_detected"
        ]
    ):

        print(
            "DISTURBANCE PATTERN: SUPPORTED"
        )


        print(
            "Face Yaw detects head orientation, "
            "while shoulder depth provides "
            "additional torso-rotation information."
        )


        print(
            "Next candidate:"
        )


        print(
            "Neck Rotation = "
            "Head orientation relative to torso."
        )


    else:

        print(
            "DISTURBANCE PATTERN: NEEDS REVIEW"
        )


        print(
            "Do not lock the Neck Rotation formula yet."
        )


    print(
        "================================================"
    )


# ==========================================================
# Save CSV
# ==========================================================

def save_results_to_csv(
    results
):

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


    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    output_path = (
        results_dir
        / (
            "neck_rotation_disturbance_"
            + timestamp
            + ".csv"
        )
    )


    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        fieldnames = [

            "state",
            "samples",

            "face_yaw_median",
            "face_yaw_mean",
            "face_yaw_std",

            "pitch_median",
            "roll_median",

            "shoulder_depth_angle_median",
            "shoulder_depth_angle_mean",
            "shoulder_depth_angle_std",
        ]


        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames
        )


        writer.writeheader()


        for result in results:

            summary = (
                result[
                    "summary"
                ]
            )


            writer.writerow(
                {

                    "state": (
                        result[
                            "state"
                        ]
                    ),

                    "samples": (
                        summary[
                            "samples"
                        ]
                    ),

                    "face_yaw_median": (
                        summary[
                            "yaw"
                        ][
                            "median"
                        ]
                    ),

                    "face_yaw_mean": (
                        summary[
                            "yaw"
                        ][
                            "mean"
                        ]
                    ),

                    "face_yaw_std": (
                        summary[
                            "yaw"
                        ][
                            "std"
                        ]
                    ),

                    "pitch_median": (
                        summary[
                            "pitch"
                        ][
                            "median"
                        ]
                    ),

                    "roll_median": (
                        summary[
                            "roll"
                        ][
                            "median"
                        ]
                    ),

                    "shoulder_depth_angle_median": (
                        summary[
                            "torso"
                        ][
                            "median"
                        ]
                    ),

                    "shoulder_depth_angle_mean": (
                        summary[
                            "torso"
                        ][
                            "mean"
                        ]
                    ),

                    "shoulder_depth_angle_std": (
                        summary[
                            "torso"
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


# ==========================================================
# Draw Pose Shoulders
# ==========================================================

def draw_shoulders(
    display_frame,
    pose_points
):

    if pose_points is None:

        return display_frame


    if (
        "left_shoulder" not in pose_points
        or
        "right_shoulder" not in pose_points
    ):

        return display_frame


    height, width = (
        display_frame.shape[:2]
    )


    left = (
        pose_points[
            "left_shoulder"
        ]
    )


    right = (
        pose_points[
            "right_shoulder"
        ]
    )


    # ======================================================
    # pose_points มาจาก RAW frame
    #
    # display_frame ถูก mirror
    #
    # ดังนั้นต้อง mirror X ตอนวาดเท่านั้น
    # ======================================================

    left_x = (
        width
        - 1
        - int(
            left["x"]
        )
    )


    left_y = int(
        left["y"]
    )


    right_x = (
        width
        - 1
        - int(
            right["x"]
        )
    )


    right_y = int(
        right["y"]
    )


    # Shoulder line
    cv2.line(
        display_frame,
        (
            left_x,
            left_y
        ),
        (
            right_x,
            right_y
        ),
        (
            255,
            255,
            0
        ),
        2
    )


    # Left Shoulder
    cv2.circle(
        display_frame,
        (
            left_x,
            left_y
        ),
        7,
        (
            255,
            0,
            255
        ),
        -1
    )


    # Right Shoulder
    cv2.circle(
        display_frame,
        (
            right_x,
            right_y
        ),
        7,
        (
            0,
            165,
            255
        ),
        -1
    )


    return display_frame


# ==========================================================
# Main
# ==========================================================

def main():

    # ======================================================
    # Model Checks
    # ======================================================

    if not FACE_MODEL_PATH.exists():

        print(
            "Error: Face model not found"
        )


        print(
            FACE_MODEL_PATH
        )


        return


    if not POSE_MODEL_PATH.exists():

        print(
            "Error: Pose model not found"
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
    # Webcam
    # ======================================================

    cap = cv2.VideoCapture(
        0
    )


    if not cap.isOpened():

        print(
            "Error: Can't open camera"
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
    # Test State
    # ======================================================

    test_index = 0

    results = []


    collecting = False

    collection_start_time = None

    current_samples = []


    test_complete = False

    results_saved = False


    status_message = (
        "Press SPACE to capture current state"
    )


    # ======================================================
    # Main Loop
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


        frame_height, frame_width = (
            raw_frame.shape[:2]
        )


        # ==================================================
        # IMPORTANT
        #
        # Face + Pose วิเคราะห์ RAW FRAME เดียวกัน
        #
        # ห้าม flip ก่อน detect
        # ==================================================

        face_result = (
            face_detector.detect(
                raw_frame
            )
        )


        pose_points = (
            pose_detector.detect(
                raw_frame
            )
        )


        # ==================================================
        # Face Points
        # ==================================================

        face_points = (
            extract_face_points(
                face_result,
                frame_width,
                frame_height
            )
        )


        # ==================================================
        # Face Validator
        # ==================================================

        head_validation = (
            validate_head_orientation(
                face_points
            )
        )


        # ==================================================
        # Face Orientation
        # ==================================================

        orientation = (
            extract_face_orientation(
                face_result
            )
        )


        # ==================================================
        # Torso Candidate
        # ==================================================

        torso = (
            calculate_shoulder_depth_angle(
                pose_points
            )
        )


        # ==================================================
        # Overall validity
        # ==================================================

        face_valid = (
            orientation is not None
            and
            head_validation[
                "valid"
            ]
        )


        pose_valid = (
            torso is not None
        )


        sample_valid = (
            face_valid
            and
            pose_valid
        )


        # ==================================================
        # Capture
        # ==================================================

        if collecting:

            elapsed = (
                time.perf_counter()
                -
                collection_start_time
            )


            if sample_valid:

                current_samples.append(
                    {

                        "yaw": (
                            orientation[
                                "yaw"
                            ]
                        ),

                        "pitch": (
                            orientation[
                                "pitch"
                            ]
                        ),

                        "roll": (
                            orientation[
                                "roll"
                            ]
                        ),

                        "torso_depth_angle": (
                            torso[
                                "depth_angle"
                            ]
                        ),
                    }
                )


            # ==================================================
            # Complete current capture
            # ==================================================

            if (
                elapsed
                >= SAMPLE_DURATION_SECONDS
            ):

                collecting = False


                # ==============================================
                # Not enough valid data
                # ==============================================

                if (
                    len(
                        current_samples
                    )
                    <
                    MIN_VALID_SAMPLES
                ):

                    status_message = (
                        "RETRY: not enough "
                        f"valid samples ({len(current_samples)})"
                    )


                    print(
                        "\nCapture failed."
                    )


                    print(
                        "Valid samples:",
                        len(
                            current_samples
                        )
                    )


                    current_samples = []


                # ==============================================
                # Capture success
                # ==============================================

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


                    test_index += 1

                    current_samples = []


                    # ==========================================
                    # Complete all states
                    # ==========================================

                    if (
                        test_index
                        >= len(
                            TEST_SEQUENCE
                        )
                    ):

                        test_complete = True


                        status_message = (
                            "DISTURBANCE TEST COMPLETE"
                        )


                        print_final_report(
                            results
                        )


                        if not results_saved:

                            save_results_to_csv(
                                results
                            )


                            results_saved = True


                    else:

                        next_step = (
                            TEST_SEQUENCE[
                                test_index
                            ]
                        )


                        status_message = (
                            "Next: "
                            + next_step[
                                "state"
                            ]
                        )


        # ==================================================
        # Display Mirror
        # ==================================================

        display_frame = cv2.flip(
            raw_frame,
            1
        )


        # ==================================================
        # Face drawing
        # ==================================================

        display_frame = (
            draw_face_points(
                display_frame,
                face_points,
                mirrored=True
            )
        )


        # ==================================================
        # Shoulder drawing
        # ==================================================

        display_frame = (
            draw_shoulders(
                display_frame,
                pose_points
            )
        )


        # ==================================================
        # Status
        # ==================================================

        cv2.putText(
            display_frame,
            (
                "Face: "
                +
                (
                    "VALID"
                    if face_valid
                    else "INVALID"
                )
            ),
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (
                0,
                255,
                0
            )
            if face_valid
            else (
                0,
                0,
                255
            ),
            2
        )


        cv2.putText(
            display_frame,
            (
                "Pose Shoulders: "
                +
                (
                    "VALID"
                    if pose_valid
                    else "INVALID"
                )
            ),
            (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.60,
            (
                0,
                255,
                0
            )
            if pose_valid
            else (
                0,
                0,
                255
            ),
            2
        )


        # ==================================================
        # Live Metrics
        # ==================================================

        if face_valid:

            cv2.putText(
                display_frame,
                (
                    "Face Yaw: "
                    f"{orientation['yaw']:+.2f} deg"
                ),
                (20, 110),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.70,
                (
                    0,
                    255,
                    255
                ),
                2
            )


        if pose_valid:

            cv2.putText(
                display_frame,
                (
                    "Shoulder Depth Angle: "
                    f"{torso['depth_angle']:+.2f} deg"
                ),
                (20, 145),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (
                    255,
                    255,
                    0
                ),
                2
            )


            cv2.putText(
                display_frame,
                (
                    "Shoulder dz: "
                    f"{torso['world_dz']:+.4f} m"
                ),
                (20, 175),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (
                    255,
                    255,
                    255
                ),
                1
            )


        # ==================================================
        # Current Test State
        # ==================================================

        if not test_complete:

            state = (
                TEST_SEQUENCE[
                    test_index
                ][
                    "state"
                ]
            )


            state_text = (
                "State: "
                + state
            )


        else:

            state_text = (
                "Disturbance Test Complete"
            )


        cv2.putText(
            display_frame,
            state_text,
            (20, 220),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            (
                0,
                255,
                255
            ),
            2
        )


        # ==================================================
        # Progress
        # ==================================================

        if collecting:

            elapsed = min(
                (
                    time.perf_counter()
                    -
                    collection_start_time
                ),
                SAMPLE_DURATION_SECONDS
            )


            progress_text = (
                "CAPTURING "
                f"{elapsed:.1f}/"
                f"{SAMPLE_DURATION_SECONDS:.1f}s "
                f"samples={len(current_samples)}"
            )


        else:

            progress_text = (
                status_message
            )


        cv2.putText(
            display_frame,
            progress_text,
            (20, 255),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (
                255,
                255,
                255
            ),
            2
        )


        # ==================================================
        # Instructions
        # ==================================================

        cv2.putText(
            display_frame,
            "SPACE=Capture   P=Print   R=Reset   Q=Quit",
            (
                20,
                frame_height - 30
            ),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (
                255,
                255,
                255
            ),
            1,
            cv2.LINE_AA
        )


        cv2.imshow(
            "PostGuard - Neck Rotation Disturbance",
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
        # SPACE = capture current state
        # ==================================================

        if (
            key == ord(" ")
            and
            not collecting
            and
            not test_complete
        ):

            if not sample_valid:

                status_message = (
                    "Cannot capture: "
                    "Face/Pose INVALID"
                )


                print(
                    "Cannot capture:"
                    " Face/Pose INVALID"
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
                    "State:",
                    step[
                        "state"
                    ]
                )


                collecting = True


                collection_start_time = (
                    time.perf_counter()
                )


                current_samples = []


        # ==================================================
        # P = Print live values
        # ==================================================

        if (
            key in (
                ord("p"),
                ord("P")
            )
        ):

            print(
                "\nCURRENT"
            )


            if face_valid:

                print(
                    "Face Yaw:",
                    f"{orientation['yaw']:+.3f}"
                )


                print(
                    "Pitch:",
                    f"{orientation['pitch']:+.3f}"
                )


                print(
                    "Roll:",
                    f"{orientation['roll']:+.3f}"
                )


            if pose_valid:

                print(
                    "Shoulder Depth Angle:",
                    f"{torso['depth_angle']:+.3f}"
                )


                print(
                    "Shoulder dx:",
                    f"{torso['world_dx']:+.4f}"
                )


                print(
                    "Shoulder dz:",
                    f"{torso['world_dz']:+.4f}"
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

            collecting = False

            collection_start_time = None

            current_samples = []

            test_complete = False

            results_saved = False


            status_message = (
                "Test reset - start NORMAL_1"
            )


            print(
                "\nDisturbance test RESET"
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